package orgdatacore

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"sort"
	"strings"
	"sync"
	"time"
)

// entityRef holds the identity-keyed view of a hierarchy entity used for
// relationship traversal. Names are not unique across types, so parent and
// child edges are followed by stable ID rather than by name.
type entityRef struct {
	name     string
	typ      EntityType
	parentID string
	stableID string
}

// nameTypeKey resolves a (name, type) pair to a stable ID.
type nameTypeKey struct {
	name string
	typ  EntityType
}

type Service struct {
	mu                sync.RWMutex
	data              *Data
	version           DataVersion
	logger            *slog.Logger
	watcherRunning    bool
	watcherCancel     context.CancelFunc
	slackChannelIndex map[string][]string

	// Derived identity indexes, rebuilt on every load. Populated only when the
	// index carries stable IDs (useStableIDs); otherwise traversal falls back
	// to the legacy name+type behavior.
	entityByID   map[string]entityRef
	childrenByID map[string][]string
	idByNameType map[nameTypeKey]string
	useStableIDs bool

	// Historical snapshot cache for AsOf, keyed by version ID (LRU).
	historyMu        sync.Mutex
	historyCache     map[string]*Service
	historyOrder     []string
	historyCacheSize int
}

func NewService(opts ...ServiceOption) *Service {
	cfg := defaultServiceConfig()
	for _, opt := range opts {
		opt(cfg)
	}
	return &Service{logger: cfg.logger, historyCacheSize: cfg.historyCacheSize}
}

func (s *Service) LoadFromDataSource(ctx context.Context, source DataSource) error {
	reader, err := source.Load(ctx)
	if err != nil {
		return NewLoadError(source.String(), err)
	}
	defer func() {
		if closeErr := reader.Close(); closeErr != nil {
			s.logger.Warn("failed to close reader", "source", source.String(), "error", closeErr)
		}
	}()

	return s.loadFromReader(reader, source.String())
}

// loadFromReader decodes, validates, and swaps in the index JSON read from
// reader. It is the shared core of LoadFromDataSource and AsOf. sourceName is
// used only for error messages and logging; reader is not closed here.
func (s *Service) loadFromReader(reader io.Reader, sourceName string) error {
	var orgData Data
	if err := json.NewDecoder(reader).Decode(&orgData); err != nil {
		return NewLoadError(sourceName, fmt.Errorf("failed to parse JSON: %w", err))
	}

	if err := validateData(&orgData); err != nil {
		return NewLoadError(sourceName, err)
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	s.data = &orgData
	s.version = DataVersion{
		LoadTime:      time.Now(),
		OrgCount:      len(orgData.Lookups.Orgs),
		EmployeeCount: len(orgData.Lookups.Employees),
	}

	s.slackChannelIndex = make(map[string][]string)
	for _, team := range orgData.Lookups.Teams {
		if team.Group.Slack == nil {
			continue
		}
		for _, ch := range team.Group.Slack.Channels {
			if ch.Channel != "" {
				normalized := normalizeSlackChannel(ch.Channel)
				s.slackChannelIndex[normalized] = append(s.slackChannelIndex[normalized], team.Name)
			}
		}
	}

	s.buildDerivedIndexes()

	s.logger.Info("data loaded", "source", sourceName, "employees", s.version.EmployeeCount, "orgs", s.version.OrgCount)
	return nil
}

// buildDerivedIndexes constructs the stable-ID relationship indexes from the
// loaded data. Must be called with s.mu held. It enables useStableIDs only when
// the index is a sound identity graph: every entity carries a unique stable_id,
// every parent edge carries a parent_id, and every parent_id resolves to a
// known entity. Any defect (or an old-format index) falls back to name+type
// traversal rather than silently returning wrong ancestry.
func (s *Service) buildDerivedIndexes() {
	s.entityByID = make(map[string]entityRef)
	s.childrenByID = make(map[string][]string)
	s.idByNameType = make(map[nameTypeKey]string)
	s.useStableIDs = false
	if s.data == nil {
		return
	}

	anyStableID := true
	allEdgesIdentified := true
	duplicateStableID := false

	register := func(name string, typ EntityType, stableID, parentID string, hasParent bool) {
		if stableID == "" {
			anyStableID = false
			return
		}
		if _, exists := s.entityByID[stableID]; exists {
			duplicateStableID = true
		}
		s.entityByID[stableID] = entityRef{name: name, typ: typ, parentID: parentID, stableID: stableID}
		s.idByNameType[nameTypeKey{name: name, typ: typ}] = stableID
		if hasParent && parentID == "" {
			allEdgesIdentified = false
		}
	}

	for name, e := range s.data.Lookups.Teams {
		register(name, EntityTeam, e.StableID, e.ParentID, e.Parent != nil)
	}
	for name, e := range s.data.Lookups.Orgs {
		register(name, EntityOrg, e.StableID, e.ParentID, e.Parent != nil)
	}
	for name, e := range s.data.Lookups.Pillars {
		register(name, EntityPillar, e.StableID, e.ParentID, e.Parent != nil)
	}
	for name, e := range s.data.Lookups.TeamGroups {
		register(name, EntityTeamGroup, e.StableID, e.ParentID, e.Parent != nil)
	}

	// Every parent_id must resolve to a known entity, otherwise traversal would
	// silently truncate ancestry or drop a descendants branch.
	allParentsResolve := true
	for _, ref := range s.entityByID {
		if ref.parentID != "" {
			if _, ok := s.entityByID[ref.parentID]; !ok {
				allParentsResolve = false
				break
			}
		}
	}

	if len(s.entityByID) == 0 || !anyStableID || !allEdgesIdentified ||
		duplicateStableID || !allParentsResolve {
		// Old-format or malformed index: use legacy traversal.
		s.entityByID = make(map[string]entityRef)
		s.childrenByID = make(map[string][]string)
		s.idByNameType = make(map[nameTypeKey]string)
		return
	}

	for id, ref := range s.entityByID {
		if ref.parentID != "" {
			s.childrenByID[ref.parentID] = append(s.childrenByID[ref.parentID], id)
		}
	}
	s.useStableIDs = true
}

func (s *Service) StartDataSourceWatcher(ctx context.Context, source DataSource) error {
	s.mu.Lock()
	if s.watcherRunning {
		s.mu.Unlock()
		return ErrWatcherAlreadyRunning
	}
	s.watcherRunning = true

	// Create a cancellable context so StopWatcher can terminate the watcher
	watchCtx, cancel := context.WithCancel(ctx)
	s.watcherCancel = cancel
	s.mu.Unlock()

	if err := s.LoadFromDataSource(watchCtx, source); err != nil {
		s.mu.Lock()
		s.watcherRunning = false
		s.watcherCancel = nil
		s.mu.Unlock()
		cancel() // Clean up the context
		return err
	}

	err := source.Watch(watchCtx, func() error {
		if err := s.LoadFromDataSource(watchCtx, source); err != nil {
			s.logger.Error("failed to reload data", "source", source.String(), "error", err)
			return err
		}
		return nil
	})

	// Clear watcher state when Watch exits (context cancelled, error, etc.)
	s.mu.Lock()
	s.watcherRunning = false
	s.watcherCancel = nil
	s.mu.Unlock()

	return err
}

// StopWatcher stops the running watcher by cancelling its context.
// This signals the DataSource.Watch method to exit. The method is safe to call
// even if no watcher is running.
func (s *Service) StopWatcher() {
	s.mu.Lock()
	cancel := s.watcherCancel
	s.watcherCancel = nil
	s.watcherRunning = false
	s.mu.Unlock()

	if cancel != nil {
		cancel()
	}
}

func (s *Service) GetVersion() DataVersion {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.version
}

// GetDataVersion returns the producer-side version string embedded in the loaded
// index (metadata.data_version), or "" if no data is loaded. This identifies
// which upstream-generated version is currently in memory, including after AsOf.
func (s *Service) GetDataVersion() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.data == nil {
		return ""
	}
	return s.data.Metadata.DataVersion
}

// GetGeneratedAt returns the producer-side generation timestamp embedded in the
// loaded index (metadata.generated_at), or "" if no data is loaded.
func (s *Service) GetGeneratedAt() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.data == nil {
		return ""
	}
	return s.data.Metadata.GeneratedAt
}

// GetDataAge returns the duration since data was last loaded.
// Returns 0 if no data has been loaded.
func (s *Service) GetDataAge() time.Duration {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.version.LoadTime.IsZero() {
		return 0
	}
	return time.Since(s.version.LoadTime)
}

// IsDataStale returns true if data is older than maxAge, or if no data is loaded.
// Use this in health checks to detect stale data from failed reloads.
func (s *Service) IsDataStale(maxAge time.Duration) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.version.LoadTime.IsZero() {
		return true
	}
	return time.Since(s.version.LoadTime) > maxAge
}

func (s *Service) GetEmployeeByUID(uid string) *Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Employees == nil {
		return nil
	}
	if emp, exists := s.data.Lookups.Employees[uid]; exists {
		return &emp
	}
	return nil
}

func (s *Service) GetEmployeeBySlackID(slackID string) *Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.SlackIDMappings.SlackUIDToUID == nil || s.data.Lookups.Employees == nil {
		return nil
	}
	uid := s.data.Indexes.SlackIDMappings.SlackUIDToUID[slackID]
	if uid == "" {
		return nil
	}
	if emp, exists := s.data.Lookups.Employees[uid]; exists {
		return &emp
	}
	return nil
}

func (s *Service) GetEmployeeByGitHubID(githubID string) *Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.GitHubIDMappings.GitHubIDToUID == nil || s.data.Lookups.Employees == nil {
		return nil
	}
	uid := s.data.Indexes.GitHubIDMappings.GitHubIDToUID[githubID]
	if uid == "" {
		return nil
	}
	if emp, exists := s.data.Lookups.Employees[uid]; exists {
		return &emp
	}
	return nil
}

func (s *Service) GetEmployeeByEmail(email string) *Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Employees == nil {
		return nil
	}
	emailLower := strings.ToLower(email)
	for _, emp := range s.data.Lookups.Employees {
		if strings.ToLower(emp.Email) == emailLower {
			e := emp
			return &e
		}
	}
	return nil
}

func (s *Service) GetManagerForEmployee(uid string) *Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Employees == nil {
		return nil
	}
	emp, exists := s.data.Lookups.Employees[uid]
	if !exists || emp.ManagerUID == "" {
		return nil
	}
	if manager, exists := s.data.Lookups.Employees[emp.ManagerUID]; exists {
		return &manager
	}
	return nil
}

func (s *Service) GetTeamByName(teamName string) *Team {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return nil
	}
	if team, exists := s.data.Lookups.Teams[teamName]; exists {
		return &team
	}
	return nil
}

func normalizeSlackChannel(channel string) string {
	return strings.ToLower(strings.TrimPrefix(strings.TrimSpace(channel), "#"))
}

func (s *Service) GetTeamsBySlackChannel(channel string) []Team {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.slackChannelIndex == nil || channel == "" {
		return []Team{}
	}

	teamNames, exists := s.slackChannelIndex[normalizeSlackChannel(channel)]
	if !exists {
		return []Team{}
	}

	var teams []Team
	for _, name := range teamNames {
		if team, exists := s.data.Lookups.Teams[name]; exists {
			teams = append(teams, team)
		}
	}
	if teams == nil {
		return []Team{}
	}
	return teams
}

func (s *Service) GetOrgByName(orgName string) *Org {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Orgs == nil {
		return nil
	}
	if org, exists := s.data.Lookups.Orgs[orgName]; exists {
		return &org
	}
	return nil
}

func (s *Service) GetPillarByName(pillarName string) *Pillar {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Pillars == nil {
		return nil
	}
	if pillar, exists := s.data.Lookups.Pillars[pillarName]; exists {
		return &pillar
	}
	return nil
}

func (s *Service) GetTeamGroupByName(teamGroupName string) *TeamGroup {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.TeamGroups == nil {
		return nil
	}
	if tg, exists := s.data.Lookups.TeamGroups[teamGroupName]; exists {
		return &tg
	}
	return nil
}

func (s *Service) GetTeamsForUID(uid string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.getTeamsForUID(uid)
}

// getTeamsForUID is the internal version that assumes the lock is held.
func (s *Service) getTeamsForUID(uid string) []string {
	if s.data == nil || s.data.Indexes.Membership.MembershipIndex == nil {
		return []string{}
	}

	var teams []string
	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		if m.Type == string(MembershipTeam) {
			teams = append(teams, m.Name)
		}
	}
	return teams
}

func (s *Service) GetTeamsForSlackID(slackID string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return []string{}
	}
	return s.getTeamsForUID(uid)
}

func (s *Service) GetTeamMembers(teamName string) []Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return []Employee{}
	}

	team, exists := s.data.Lookups.Teams[teamName]
	if !exists {
		return []Employee{}
	}

	var members []Employee
	for _, uid := range team.Group.ResolvedPeopleUIDList {
		if emp, exists := s.data.Lookups.Employees[uid]; exists {
			members = append(members, emp)
		}
	}
	return members
}

func (s *Service) IsEmployeeInTeam(uid string, teamName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.isEmployeeInTeam(uid, teamName)
}

// isEmployeeInTeam is the internal version that assumes the lock is held.
func (s *Service) isEmployeeInTeam(uid string, teamName string) bool {
	for _, team := range s.getTeamsForUID(uid) {
		if team == teamName {
			return true
		}
	}
	return false
}

func (s *Service) IsSlackUserInTeam(slackID string, teamName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return false
	}
	return s.isEmployeeInTeam(uid, teamName)
}

func (s *Service) IsEmployeeInOrg(uid string, orgName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.isEmployeeInOrg(uid, orgName)
}

// isEmployeeInOrg is the internal version that assumes the lock is held.
func (s *Service) isEmployeeInOrg(uid string, orgName string) bool {
	if s.data == nil || s.data.Indexes.Membership.MembershipIndex == nil {
		return false
	}

	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		if MembershipType(m.Type) == MembershipOrg && m.Name == orgName {
			return true
		}
		if MembershipType(m.Type) == MembershipTeam {
			hierarchyPath := s.computeHierarchyPath(m.Name, EntityTeam.String())
			for _, entry := range hierarchyPath {
				if EntityType(strings.ToLower(entry.Type)) == EntityOrg && entry.Name == orgName {
					return true
				}
			}
		}
	}
	return false
}

func (s *Service) IsSlackUserInOrg(slackID string, orgName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return false
	}
	return s.isEmployeeInOrg(uid, orgName)
}

func (s *Service) GetUserOrganizations(slackUserID string) []OrgInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Membership.MembershipIndex == nil {
		return []OrgInfo{}
	}

	uid := s.getUIDFromSlackID(slackUserID)
	if uid == "" {
		return []OrgInfo{}
	}

	if s.useStableIDs {
		return s.userOrganizationsByID(uid)
	}

	var orgs []OrgInfo
	// Legacy mode: dedupe by (name, type). Names are not unique across types, so
	// keying on name alone would drop a legitimately distinct entity (e.g. a
	// team_group sharing a team's name) from the result.
	seen := make(map[nameTypeKey]bool)

	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		switch MembershipType(m.Type) {
		case MembershipOrg:
			key := nameTypeKey{name: m.Name, typ: EntityOrg}
			if !seen[key] {
				orgs = append(orgs, OrgInfo{Name: m.Name, Type: OrgTypeOrganization})
				seen[key] = true
			}
		case MembershipTeam:
			key := nameTypeKey{name: m.Name, typ: EntityTeam}
			if !seen[key] {
				orgs = append(orgs, OrgInfo{Name: m.Name, Type: OrgTypeTeam})
				seen[key] = true
			}
			hierarchyPath := s.computeHierarchyPath(m.Name, EntityTeam.String())
			addHierarchyPathItems(&orgs, &seen, hierarchyPath)
		}
	}
	return orgs
}

// directOrgInfoType maps a membership type to the OrgInfoType reported for a
// direct membership (as opposed to an inherited ancestor).
func directOrgInfoType(m MembershipType) OrgInfoType {
	if m == MembershipOrg {
		return OrgTypeOrganization
	}
	return OrgTypeTeam
}

// userOrganizationsByID resolves a user's organizations by stable ID: each
// membership is resolved through its stable_id (the canonical identity), and
// team ancestry is walked by parent_id. Deduping is by stable ID. Must be
// called with s.mu held and only when s.useStableIDs is true.
func (s *Service) userOrganizationsByID(uid string) []OrgInfo {
	var orgs []OrgInfo
	seen := make(map[string]bool)

	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		mType := MembershipType(m.Type)
		if mType != MembershipOrg && mType != MembershipTeam {
			continue
		}

		id := m.StableID
		if id == "" {
			// Membership without a stable_id (e.g. an older index still in the
			// stable path): resolve it by (name, type).
			id = s.idByNameType[nameTypeKey{name: m.Name, typ: EntityType(strings.ToLower(m.Type))}]
		}
		ref, ok := s.entityByID[id]
		if !ok {
			continue
		}

		if !seen[id] {
			seen[id] = true
			orgs = append(orgs, OrgInfo{Name: ref.name, Type: directOrgInfoType(mType), StableID: ref.stableID})
		}

		if mType != MembershipTeam {
			continue
		}
		// Walk ancestors with a per-walk visited set. Using the shared seen set
		// as the stop condition would halt at an ancestor already recorded by an
		// earlier (e.g. direct org) membership and drop its higher ancestors.
		// visited also terminates cyclic parent links.
		visited := make(map[string]bool)
		for pid := ref.parentID; pid != "" && !visited[pid]; {
			visited[pid] = true
			parent, ok := s.entityByID[pid]
			if !ok {
				break
			}
			if !seen[pid] {
				seen[pid] = true
				orgs = append(orgs, OrgInfo{Name: parent.name, Type: ancestorOrgInfoType(parent.typ), StableID: parent.stableID})
			}
			pid = parent.parentID
		}
	}
	return orgs
}

// ancestorOrgInfoType maps a hierarchy-ancestor entity type to the OrgInfoType
// reported by GetUserOrganizations (a team seen as an ancestor is a parent team).
func ancestorOrgInfoType(t EntityType) OrgInfoType {
	switch t {
	case EntityOrg:
		return OrgTypeOrganization
	case EntityPillar:
		return OrgTypePillar
	case EntityTeamGroup:
		return OrgTypeTeamGroup
	case EntityTeam:
		return OrgTypeParentTeam
	default:
		return OrgTypeOrganization
	}
}

func addHierarchyPathItems(orgs *[]OrgInfo, seen *map[nameTypeKey]bool, hierarchyPath []HierarchyPathEntry) {
	for i, entry := range hierarchyPath {
		if i == 0 {
			continue
		}
		entryType := EntityType(strings.ToLower(entry.Type))
		// entry.Type is a free-form string; skip unknown/empty types rather than
		// mislabeling them (keeps parity with the Python implementation).
		if !entryType.IsValid() {
			continue
		}
		key := nameTypeKey{name: entry.Name, typ: entryType}
		if !(*seen)[key] {
			*orgs = append(*orgs, OrgInfo{Name: entry.Name, Type: ancestorOrgInfoType(entryType), StableID: entry.StableID})
			(*seen)[key] = true
		}
	}
}

func (s *Service) getUIDFromSlackID(slackID string) string {
	if s.data == nil || s.data.Indexes.SlackIDMappings.SlackUIDToUID == nil {
		return ""
	}
	return s.data.Indexes.SlackIDMappings.SlackUIDToUID[slackID]
}

// getEntityParent returns the parent info for an entity by name and type.
// Must be called with s.mu held.
func (s *Service) getEntityParent(entityName, entityType string) *ParentInfo {
	if s.data == nil {
		return nil
	}

	switch strings.ToLower(entityType) {
	case "team":
		if team, ok := s.data.Lookups.Teams[entityName]; ok {
			return team.Parent
		}
	case "org":
		if org, ok := s.data.Lookups.Orgs[entityName]; ok {
			return org.Parent
		}
	case "pillar":
		if pillar, ok := s.data.Lookups.Pillars[entityName]; ok {
			return pillar.Parent
		}
	case "team_group":
		if tg, ok := s.data.Lookups.TeamGroups[entityName]; ok {
			return tg.Parent
		}
	}
	return nil
}

// getEntityType looks up the type for an entity by scanning all lookups.
// Must be called with s.mu held.
func (s *Service) getEntityType(entityName string) string {
	if s.data == nil {
		return ""
	}
	if _, ok := s.data.Lookups.Teams[entityName]; ok {
		return "team"
	}
	if _, ok := s.data.Lookups.Orgs[entityName]; ok {
		return "org"
	}
	if _, ok := s.data.Lookups.Pillars[entityName]; ok {
		return "pillar"
	}
	if _, ok := s.data.Lookups.TeamGroups[entityName]; ok {
		return "team_group"
	}
	return ""
}

// computeHierarchyPath builds the hierarchy path by walking parent references.
// Must be called with s.mu held.
func (s *Service) computeHierarchyPath(entityName, entityType string) []HierarchyPathEntry {
	if s.data == nil {
		return []HierarchyPathEntry{}
	}

	if s.useStableIDs {
		return s.computeHierarchyPathByID(entityName, entityType)
	}

	// Check entity exists - either infer type or validate provided type
	if entityType == "" {
		entityType = s.getEntityType(entityName)
		if entityType == "" {
			return []HierarchyPathEntry{}
		}
	} else {
		// Validate entity exists with given type
		actualType := s.getEntityType(entityName)
		if actualType == "" || !strings.EqualFold(actualType, entityType) {
			return []HierarchyPathEntry{}
		}
		entityType = actualType
	}

	path := []HierarchyPathEntry{{Name: entityName, Type: entityType}}
	// Guard against cycles by tracking visited entities by both name and type.
	// Different entity types can share a name (e.g. a team and its parent
	// team_group), so keying on name alone would stop the walk prematurely.
	visited := map[HierarchyPathEntry]bool{{Name: entityName, Type: entityType}: true}

	currentName := entityName
	currentType := entityType

	for {
		parent := s.getEntityParent(currentName, currentType)
		if parent == nil {
			break
		}
		parentEntry := HierarchyPathEntry{Name: parent.Name, Type: parent.Type}
		if visited[parentEntry] {
			break
		}
		visited[parentEntry] = true
		path = append(path, parentEntry)
		currentName = parent.Name
		currentType = parent.Type
	}

	return path
}

// computeHierarchyPathByID walks the parent chain by stable ID. Must be called
// with s.mu held and only when s.useStableIDs is true. Because relationships
// are keyed by identity, an explicitly requested type resolves the correct
// entity even when its name is shared across types.
func (s *Service) computeHierarchyPathByID(entityName, entityType string) []HierarchyPathEntry {
	startID := s.resolveStartID(entityName, entityType)
	if startID == "" {
		return []HierarchyPathEntry{}
	}

	path := []HierarchyPathEntry{}
	visited := map[string]bool{}
	for id := startID; id != "" && !visited[id]; {
		visited[id] = true
		ref, ok := s.entityByID[id]
		if !ok {
			break
		}
		path = append(path, HierarchyPathEntry{Name: ref.name, Type: ref.typ.String(), StableID: ref.stableID})
		id = ref.parentID
	}
	return path
}

// resolveStartID maps a (name, type) pair to a stable ID. When entityType is
// empty the type is inferred by name (first match, as with the legacy path).
// Must be called with s.mu held.
func (s *Service) resolveStartID(entityName, entityType string) string {
	if entityType == "" {
		entityType = s.getEntityType(entityName)
		if entityType == "" {
			return ""
		}
	}
	return s.idByNameType[nameTypeKey{name: entityName, typ: EntityType(strings.ToLower(entityType))}]
}

func (s *Service) GetAllEmployeeUIDs() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Employees == nil {
		return []string{}
	}
	uids := make([]string, 0, len(s.data.Lookups.Employees))
	for uid := range s.data.Lookups.Employees {
		uids = append(uids, uid)
	}
	return uids
}

func (s *Service) GetAllTeamNames() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return []string{}
	}
	names := make([]string, 0, len(s.data.Lookups.Teams))
	for name := range s.data.Lookups.Teams {
		names = append(names, name)
	}
	return names
}

func (s *Service) GetAllOrgNames() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Orgs == nil {
		return []string{}
	}
	names := make([]string, 0, len(s.data.Lookups.Orgs))
	for name := range s.data.Lookups.Orgs {
		names = append(names, name)
	}
	return names
}

func (s *Service) GetAllPillarNames() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Pillars == nil {
		return []string{}
	}
	names := make([]string, 0, len(s.data.Lookups.Pillars))
	for name := range s.data.Lookups.Pillars {
		names = append(names, name)
	}
	return names
}

func (s *Service) GetAllTeamGroupNames() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.TeamGroups == nil {
		return []string{}
	}
	names := make([]string, 0, len(s.data.Lookups.TeamGroups))
	for name := range s.data.Lookups.TeamGroups {
		names = append(names, name)
	}
	return names
}

// GetHierarchyPath returns the ordered hierarchy path from entity to root.
func (s *Service) GetHierarchyPath(entityName string, entityType string) []HierarchyPathEntry {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.computeHierarchyPath(entityName, entityType)
}

// GetDescendantsTree returns all descendants of an entity as a nested tree.
func (s *Service) GetDescendantsTree(entityName string) *HierarchyNode {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil {
		return nil
	}

	if s.useStableIDs {
		return s.getDescendantsTreeByID(entityName)
	}

	entityType := s.getEntityType(entityName)
	if entityType == "" {
		return nil
	}

	// Build children map by scanning all entities
	childrenMap := make(map[string][]struct{ name, typ string })

	for name, team := range s.data.Lookups.Teams {
		if team.Parent != nil {
			childrenMap[team.Parent.Name] = append(childrenMap[team.Parent.Name], struct{ name, typ string }{name, "team"})
		}
	}
	for name, org := range s.data.Lookups.Orgs {
		if org.Parent != nil {
			childrenMap[org.Parent.Name] = append(childrenMap[org.Parent.Name], struct{ name, typ string }{name, "org"})
		}
	}
	for name, pillar := range s.data.Lookups.Pillars {
		if pillar.Parent != nil {
			childrenMap[pillar.Parent.Name] = append(childrenMap[pillar.Parent.Name], struct{ name, typ string }{name, "pillar"})
		}
	}
	for name, tg := range s.data.Lookups.TeamGroups {
		if tg.Parent != nil {
			childrenMap[tg.Parent.Name] = append(childrenMap[tg.Parent.Name], struct{ name, typ string }{name, "team_group"})
		}
	}

	// Build tree recursively
	var buildNode func(name, typ string, visited map[string]bool) HierarchyNode
	buildNode = func(name, typ string, visited map[string]bool) HierarchyNode {
		if visited[name] {
			return HierarchyNode{Name: name, Type: typ, Children: []HierarchyNode{}}
		}
		visited[name] = true

		children := childrenMap[name]
		childNodes := make([]HierarchyNode, 0, len(children))
		for _, c := range children {
			childNodes = append(childNodes, buildNode(c.name, c.typ, visited))
		}

		return HierarchyNode{Name: name, Type: typ, Children: childNodes}
	}

	node := buildNode(entityName, entityType, make(map[string]bool))
	return &node
}

// getDescendantsTreeByID builds the descendants tree using stable-ID edges.
// Must be called with s.mu held and only when s.useStableIDs is true. Keying
// children and cycle detection by stable ID keeps the subtrees of same-named
// parents distinct. The root type is still inferred by name (the public API
// accepts only a name), but the tree below it is collision-safe.
func (s *Service) getDescendantsTreeByID(entityName string) *HierarchyNode {
	entityType := s.getEntityType(entityName)
	if entityType == "" {
		return nil
	}
	startID := s.idByNameType[nameTypeKey{name: entityName, typ: EntityType(entityType)}]
	if startID == "" {
		return nil
	}

	var buildNode func(id string, visited map[string]bool) HierarchyNode
	buildNode = func(id string, visited map[string]bool) HierarchyNode {
		ref := s.entityByID[id]
		if visited[id] {
			return HierarchyNode{Name: ref.name, Type: ref.typ.String(), StableID: ref.stableID, Children: []HierarchyNode{}}
		}
		visited[id] = true

		childIDs := append([]string(nil), s.childrenByID[id]...)
		// Deterministic ordering (map iteration is random).
		sort.Slice(childIDs, func(i, j int) bool {
			a, b := s.entityByID[childIDs[i]], s.entityByID[childIDs[j]]
			if a.name != b.name {
				return a.name < b.name
			}
			return a.typ < b.typ
		})

		childNodes := make([]HierarchyNode, 0, len(childIDs))
		for _, cid := range childIDs {
			childNodes = append(childNodes, buildNode(cid, visited))
		}
		return HierarchyNode{Name: ref.name, Type: ref.typ.String(), StableID: ref.stableID, Children: childNodes}
	}

	node := buildNode(startID, make(map[string]bool))
	return &node
}

// GetComponentByName returns a component by name.
func (s *Service) GetComponentByName(name string) *Component {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Components == nil {
		return nil
	}
	if component, exists := s.data.Lookups.Components[name]; exists {
		return &component
	}
	return nil
}

// GetAllComponents returns all components.
func (s *Service) GetAllComponents() []Component {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Components == nil {
		return []Component{}
	}
	components := make([]Component, 0, len(s.data.Lookups.Components))
	for _, component := range s.data.Lookups.Components {
		components = append(components, component)
	}
	return components
}

// GetAllComponentNames returns all component names.
func (s *Service) GetAllComponentNames() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Components == nil {
		return []string{}
	}
	names := make([]string, 0, len(s.data.Lookups.Components))
	for name := range s.data.Lookups.Components {
		names = append(names, name)
	}
	return names
}

// GetJiraProjects returns all Jira project keys.
func (s *Service) GetJiraProjects() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Jira == nil {
		return []string{}
	}
	projects := make([]string, 0, len(s.data.Indexes.Jira))
	for project := range s.data.Indexes.Jira {
		projects = append(projects, project)
	}
	return projects
}

// GetJiraComponents returns all components for a Jira project.
func (s *Service) GetJiraComponents(project string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Jira == nil {
		return []string{}
	}
	components, exists := s.data.Indexes.Jira[project]
	if !exists {
		return []string{}
	}
	result := make([]string, 0, len(components))
	for component := range components {
		result = append(result, component)
	}
	return result
}

// GetTeamsByJiraProject returns all teams/entities that own any component in a Jira project.
func (s *Service) GetTeamsByJiraProject(project string) []JiraOwnerInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Jira == nil {
		return []JiraOwnerInfo{}
	}
	components, exists := s.data.Indexes.Jira[project]
	if !exists {
		return []JiraOwnerInfo{}
	}

	seen := make(map[string]bool)
	var result []JiraOwnerInfo
	for _, owners := range components {
		for _, owner := range owners {
			if !seen[owner.Name] {
				seen[owner.Name] = true
				result = append(result, owner)
			}
		}
	}
	return result
}

// GetTeamsByJiraComponent returns teams/entities that own a specific Jira component.
func (s *Service) GetTeamsByJiraComponent(project, component string) []JiraOwnerInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Jira == nil {
		return []JiraOwnerInfo{}
	}
	components, exists := s.data.Indexes.Jira[project]
	if !exists {
		return []JiraOwnerInfo{}
	}
	owners, exists := components[component]
	if !exists {
		return []JiraOwnerInfo{}
	}
	// Return a copy to avoid external modification
	result := make([]JiraOwnerInfo, len(owners))
	copy(result, owners)
	return result
}

// GetJiraOwnershipForTeam returns all Jira projects and components owned by a team.
func (s *Service) GetJiraOwnershipForTeam(teamName string) []JiraOwnership {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Jira == nil {
		return []JiraOwnership{}
	}

	var result []JiraOwnership
	for project, components := range s.data.Indexes.Jira {
		for component, owners := range components {
			for _, owner := range owners {
				if owner.Name == teamName {
					result = append(result, JiraOwnership{Project: project, Component: component})
					break
				}
			}
		}
	}
	return result
}

// GetUserMemberships returns all memberships for a user.
func (s *Service) GetUserMemberships(uid string) []MembershipInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Membership.MembershipIndex == nil {
		return []MembershipInfo{}
	}
	memberships := s.data.Indexes.Membership.MembershipIndex[uid]
	if len(memberships) == 0 {
		return []MembershipInfo{}
	}
	result := make([]MembershipInfo, len(memberships))
	copy(result, memberships)
	return result
}

// GetUserTeams returns team names for a user.
func (s *Service) GetUserTeams(uid string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.getTeamsForUID(uid)
}

// GetAllEmployees returns all employees.
func (s *Service) GetAllEmployees() []Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Employees == nil {
		return []Employee{}
	}
	employees := make([]Employee, 0, len(s.data.Lookups.Employees))
	for _, emp := range s.data.Lookups.Employees {
		employees = append(employees, emp)
	}
	return employees
}

// GetAllTeams returns all teams.
func (s *Service) GetAllTeams() []Team {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return []Team{}
	}
	teams := make([]Team, 0, len(s.data.Lookups.Teams))
	for _, team := range s.data.Lookups.Teams {
		teams = append(teams, team)
	}
	return teams
}

// GetAllOrgs returns all organizations.
func (s *Service) GetAllOrgs() []Org {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Orgs == nil {
		return []Org{}
	}
	orgs := make([]Org, 0, len(s.data.Lookups.Orgs))
	for _, org := range s.data.Lookups.Orgs {
		orgs = append(orgs, org)
	}
	return orgs
}

// GetAllPillars returns all pillars.
func (s *Service) GetAllPillars() []Pillar {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Pillars == nil {
		return []Pillar{}
	}
	pillars := make([]Pillar, 0, len(s.data.Lookups.Pillars))
	for _, pillar := range s.data.Lookups.Pillars {
		pillars = append(pillars, pillar)
	}
	return pillars
}

// GetAllTeamGroups returns all team groups.
func (s *Service) GetAllTeamGroups() []TeamGroup {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.TeamGroups == nil {
		return []TeamGroup{}
	}
	tgs := make([]TeamGroup, 0, len(s.data.Lookups.TeamGroups))
	for _, tg := range s.data.Lookups.TeamGroups {
		tgs = append(tgs, tg)
	}
	return tgs
}

// GetOrgMembers returns all members of an organization.
func (s *Service) GetOrgMembers(orgName string) []Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Orgs == nil {
		return []Employee{}
	}
	org, exists := s.data.Lookups.Orgs[orgName]
	if !exists {
		return []Employee{}
	}
	var members []Employee
	for _, uid := range org.Group.ResolvedPeopleUIDList {
		if emp, exists := s.data.Lookups.Employees[uid]; exists {
			members = append(members, emp)
		}
	}
	if members == nil {
		return []Employee{}
	}
	return members
}

// GetTeamEscalation returns the escalation contacts for a team.
func (s *Service) GetTeamEscalation(teamName string) []EscalationContactInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return []EscalationContactInfo{}
	}
	team, exists := s.data.Lookups.Teams[teamName]
	if !exists {
		return []EscalationContactInfo{}
	}
	if len(team.Group.Escalation) == 0 {
		return []EscalationContactInfo{}
	}
	result := make([]EscalationContactInfo, len(team.Group.Escalation))
	copy(result, team.Group.Escalation)
	return result
}

// GetTeamsForComponent returns all teams/entities that own a component.
func (s *Service) GetTeamsForComponent(componentName string) []ComponentOwnerInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.ComponentOwnership == nil {
		return []ComponentOwnerInfo{}
	}
	owners, exists := s.data.Indexes.ComponentOwnership[componentName]
	if !exists {
		return []ComponentOwnerInfo{}
	}
	result := make([]ComponentOwnerInfo, len(owners))
	copy(result, owners)
	return result
}

// GetComponentsForTeam returns all components owned by a team.
func (s *Service) GetComponentsForTeam(teamName string) []ComponentOwnership {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.ComponentOwnership == nil {
		return []ComponentOwnership{}
	}

	var result []ComponentOwnership
	for componentName, owners := range s.data.Indexes.ComponentOwnership {
		for _, owner := range owners {
			if owner.Name == teamName {
				result = append(result, ComponentOwnership{
					Component:      componentName,
					OwnershipTypes: owner.OwnershipTypes,
				})
				break
			}
		}
	}
	if result == nil {
		return []ComponentOwnership{}
	}
	return result
}

// getEntityGroup returns the Group for an entity by name and type.
// Must be called with s.mu held.
func (s *Service) getEntityGroup(entityName, entityType string) *Group {
	if s.data == nil {
		return nil
	}
	switch strings.ToLower(entityType) {
	case "team":
		if team, ok := s.data.Lookups.Teams[entityName]; ok {
			return &team.Group
		}
	case "org":
		if org, ok := s.data.Lookups.Orgs[entityName]; ok {
			return &org.Group
		}
	case "pillar":
		if pillar, ok := s.data.Lookups.Pillars[entityName]; ok {
			return &pillar.Group
		}
	case "team_group":
		if tg, ok := s.data.Lookups.TeamGroups[entityName]; ok {
			return &tg.Group
		}
	}
	return nil
}

// GetContextForTeam returns resolved context items for a team (including inherited).
func (s *Service) GetContextForTeam(teamName string) []ContextItemInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Lookups.Teams == nil {
		return []ContextItemInfo{}
	}
	team, exists := s.data.Lookups.Teams[teamName]
	if !exists {
		return []ContextItemInfo{}
	}
	if len(team.Group.ResolvedContext) == 0 {
		return []ContextItemInfo{}
	}
	result := make([]ContextItemInfo, len(team.Group.ResolvedContext))
	copy(result, team.Group.ResolvedContext)
	return result
}

// GetContextForEntity returns resolved context items for any entity type.
func (s *Service) GetContextForEntity(entityName string, entityType string) []ContextItemInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	group := s.getEntityGroup(entityName, entityType)
	if group == nil {
		return []ContextItemInfo{}
	}
	if len(group.ResolvedContext) == 0 {
		return []ContextItemInfo{}
	}
	result := make([]ContextItemInfo, len(group.ResolvedContext))
	copy(result, group.ResolvedContext)
	return result
}

// GetContextByType returns resolved context items filtered by a specific context type.
func (s *Service) GetContextByType(entityName string, contextType string, entityType string) []ContextItemInfo {
	s.mu.RLock()
	defer s.mu.RUnlock()

	group := s.getEntityGroup(entityName, entityType)
	if group == nil {
		return []ContextItemInfo{}
	}
	var result []ContextItemInfo
	for _, item := range group.ResolvedContext {
		for _, t := range item.Types {
			if t == contextType {
				result = append(result, item)
				break
			}
		}
	}
	if result == nil {
		return []ContextItemInfo{}
	}
	return result
}

// GetAllContextTypesForEntity returns distinct context types available for an entity.
func (s *Service) GetAllContextTypesForEntity(entityName string, entityType string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	group := s.getEntityGroup(entityName, entityType)
	if group == nil {
		return []string{}
	}
	seen := make(map[string]bool)
	var result []string
	for _, item := range group.ResolvedContext {
		for _, t := range item.Types {
			if !seen[t] {
				seen[t] = true
				result = append(result, t)
			}
		}
	}
	if result == nil {
		return []string{}
	}
	return result
}

// GetContextTypeDescriptions returns the description registry for all context types.
func (s *Service) GetContextTypeDescriptions() map[string]string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Metadata.ContextTypeDescriptions == nil {
		return map[string]string{}
	}
	result := make(map[string]string, len(s.data.Metadata.ContextTypeDescriptions))
	for k, v := range s.data.Metadata.ContextTypeDescriptions {
		result[k] = v
	}
	return result
}

// validateData checks that required data structures are present.
func validateData(data *Data) error {
	if data.Metadata.PIIFree {
		if len(data.Lookups.Employees) > 0 {
			return fmt.Errorf("%w: pii_free is set but lookups.employees is not empty", ErrInvalidData)
		}
		if len(data.Indexes.Membership.MembershipIndex) > 0 {
			return fmt.Errorf("%w: pii_free is set but membership_index is not empty", ErrInvalidData)
		}
		return nil
	}
	if len(data.Lookups.Employees) == 0 {
		return fmt.Errorf("%w: missing lookups.employees", ErrInvalidData)
	}
	if len(data.Indexes.Membership.MembershipIndex) == 0 {
		return fmt.Errorf("%w: missing indexes.membership.membership_index", ErrInvalidData)
	}
	return nil
}
