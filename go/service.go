package orgdatacore

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"time"
)

type Service struct {
	mu             sync.RWMutex
	data           *Data
	version        DataVersion
	logger         *slog.Logger
	watcherRunning bool
}

func NewService(opts ...ServiceOption) *Service {
	cfg := defaultServiceConfig()
	for _, opt := range opts {
		opt(cfg)
	}
	return &Service{logger: cfg.logger}
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

	var orgData Data
	if err := json.NewDecoder(reader).Decode(&orgData); err != nil {
		return NewLoadError(source.String(), fmt.Errorf("failed to parse JSON: %w", err))
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	s.data = &orgData
	s.version = DataVersion{
		LoadTime:      time.Now(),
		OrgCount:      len(orgData.Lookups.Orgs),
		EmployeeCount: len(orgData.Lookups.Employees),
	}

	s.logger.Info("data loaded", "source", source.String(), "employees", s.version.EmployeeCount, "orgs", s.version.OrgCount)
	return nil
}

func (s *Service) StartDataSourceWatcher(ctx context.Context, source DataSource) error {
	s.mu.Lock()
	if s.watcherRunning {
		s.mu.Unlock()
		return ErrWatcherAlreadyRunning
	}
	s.watcherRunning = true
	s.mu.Unlock()

	if err := s.LoadFromDataSource(ctx, source); err != nil {
		s.mu.Lock()
		s.watcherRunning = false
		s.mu.Unlock()
		return err
	}

	return source.Watch(ctx, func() error {
		if err := s.LoadFromDataSource(ctx, source); err != nil {
			s.logger.Error("failed to reload data", "source", source.String(), "error", err)
			return err
		}
		return nil
	})
}

// StopWatcher marks the watcher as stopped. Note that this only updates the
// Service's internal state - actual watcher termination depends on the
// DataSource implementation respecting context cancellation.
func (s *Service) StopWatcher() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.watcherRunning = false
}

func (s *Service) GetVersion() DataVersion {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.version
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
	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return []string{}
	}
	return s.GetTeamsForUID(uid)
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
	for _, team := range s.GetTeamsForUID(uid) {
		if team == teamName {
			return true
		}
	}
	return false
}

func (s *Service) IsSlackUserInTeam(slackID string, teamName string) bool {
	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return false
	}
	return s.IsEmployeeInTeam(uid, teamName)
}

func (s *Service) IsEmployeeInOrg(uid string, orgName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.data == nil || s.data.Indexes.Membership.MembershipIndex == nil {
		return false
	}

	teamsIndex := s.data.Indexes.Membership.RelationshipIndex["teams"]

	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		if m.Type == string(MembershipOrg) && m.Name == orgName {
			return true
		}
		if m.Type == string(MembershipTeam) {
			if rel, exists := teamsIndex[m.Name]; exists {
				for _, org := range rel.Ancestry.Orgs {
					if org == orgName {
						return true
					}
				}
			}
		}
	}
	return false
}

func (s *Service) IsSlackUserInOrg(slackID string, orgName string) bool {
	uid := s.getUIDFromSlackID(slackID)
	if uid == "" {
		return false
	}
	return s.IsEmployeeInOrg(uid, orgName)
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

	var orgs []OrgInfo
	seen := make(map[string]bool)
	teamsIndex := s.data.Indexes.Membership.RelationshipIndex["teams"]

	for _, m := range s.data.Indexes.Membership.MembershipIndex[uid] {
		switch m.Type {
		case string(MembershipOrg):
			if !seen[m.Name] {
				orgs = append(orgs, OrgInfo{Name: m.Name, Type: OrgTypeOrganization})
				seen[m.Name] = true
			}
		case string(MembershipTeam):
			if !seen[m.Name] {
				orgs = append(orgs, OrgInfo{Name: m.Name, Type: OrgTypeTeam})
				seen[m.Name] = true
			}
			if rel, exists := teamsIndex[m.Name]; exists {
				addAncestryItems(&orgs, &seen, rel.Ancestry)
			}
		}
	}
	return orgs
}

func addAncestryItems(orgs *[]OrgInfo, seen *map[string]bool, ancestry struct {
	Orgs       []string `json:"orgs"`
	Teams      []string `json:"teams"`
	Pillars    []string `json:"pillars"`
	TeamGroups []string `json:"team_groups"`
}) {
	for _, name := range ancestry.Orgs {
		if !(*seen)[name] {
			*orgs = append(*orgs, OrgInfo{Name: name, Type: OrgTypeOrganization})
			(*seen)[name] = true
		}
	}
	for _, name := range ancestry.Pillars {
		if !(*seen)[name] {
			*orgs = append(*orgs, OrgInfo{Name: name, Type: OrgTypePillar})
			(*seen)[name] = true
		}
	}
	for _, name := range ancestry.TeamGroups {
		if !(*seen)[name] {
			*orgs = append(*orgs, OrgInfo{Name: name, Type: OrgTypeTeamGroup})
			(*seen)[name] = true
		}
	}
	for _, name := range ancestry.Teams {
		if !(*seen)[name] {
			*orgs = append(*orgs, OrgInfo{Name: name, Type: OrgTypeParentTeam})
			(*seen)[name] = true
		}
	}
}

func (s *Service) getUIDFromSlackID(slackID string) string {
	if s.data == nil || s.data.Indexes.SlackIDMappings.SlackUIDToUID == nil {
		return ""
	}
	return s.data.Indexes.SlackIDMappings.SlackUIDToUID[slackID]
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
