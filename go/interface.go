package orgdatacore

import (
	"context"
	"io"
	"time"
)

// DataSource provides organizational data from external storage.
// The caller is responsible for calling Close() when done with the data source.
type DataSource interface {
	// Load returns a reader with the organizational data JSON.
	// The caller must close the returned ReadCloser when done.
	Load(ctx context.Context) (io.ReadCloser, error)

	// Watch monitors the data source for changes and calls callback on updates.
	// Blocks until context is cancelled or an error occurs.
	Watch(ctx context.Context, callback func() error) error

	// String returns a human-readable description of this data source.
	String() string

	// Close releases any resources held by this data source.
	io.Closer
}

// DataVersionRef identifies a single historical version of the index.
// ID is an opaque, source-specific version identifier (for GCS this is the
// object generation). Created is the time the version was produced.
type DataVersionRef struct {
	ID      string    `json:"id"`
	Created time.Time `json:"created"`
}

// HistoricalDataSource is an optional capability interface for data sources that
// retain previous versions of the index (e.g. a GCS bucket with object
// versioning). Sources that implement it enable Service.AsOf and
// Service.ListVersions. Sources that do not (file sources, in-memory fakes
// without history) cause those methods to return ErrTimeTravelNotSupported.
type HistoricalDataSource interface {
	DataSource

	// ListVersions returns all retained versions of the index, in no guaranteed
	// order. Callers that need ordering should sort by Created.
	ListVersions(ctx context.Context) ([]DataVersionRef, error)

	// LoadVersion returns a reader with the index JSON for a specific version.
	// The caller must close the returned ReadCloser when done.
	LoadVersion(ctx context.Context, ref DataVersionRef) (io.ReadCloser, error)
}

type ServiceInterface interface {
	GetEmployeeByUID(uid string) *Employee
	GetEmployeeBySlackID(slackID string) *Employee
	GetEmployeeByGitHubID(githubID string) *Employee
	GetEmployeeByEmail(email string) *Employee
	GetManagerForEmployee(uid string) *Employee
	GetTeamByName(teamName string) *Team
	GetTeamsBySlackChannel(channel string) []Team
	GetOrgByName(orgName string) *Org
	GetPillarByName(pillarName string) *Pillar
	GetTeamGroupByName(teamGroupName string) *TeamGroup

	GetUserMemberships(uid string) []MembershipInfo
	GetUserTeams(uid string) []string
	GetTeamsForUID(uid string) []string
	GetTeamsForSlackID(slackID string) []string
	GetTeamMembers(teamName string) []Employee
	GetOrgMembers(orgName string) []Employee
	IsEmployeeInTeam(uid string, teamName string) bool
	IsSlackUserInTeam(slackID string, teamName string) bool

	IsEmployeeInOrg(uid string, orgName string) bool
	IsSlackUserInOrg(slackID string, orgName string) bool
	GetUserOrganizations(slackUserID string) []OrgInfo

	GetTeamEscalation(teamName string) []EscalationContactInfo

	GetVersion() DataVersion
	GetDataVersion() string
	GetGeneratedAt() string
	GetDataAge() time.Duration
	IsDataStale(maxAge time.Duration) bool
	LoadFromDataSource(ctx context.Context, source DataSource) error
	StartDataSourceWatcher(ctx context.Context, source DataSource) error
	StopWatcher()

	// Time travel. ListVersions and AsOf require source to implement
	// HistoricalDataSource; otherwise they return ErrTimeTravelNotSupported.
	ListVersions(ctx context.Context, source DataSource) ([]DataVersionRef, error)
	AsOf(ctx context.Context, source DataSource, t time.Time) (ServiceInterface, error)

	GetAllEmployeeUIDs() []string
	GetAllEmployees() []Employee
	GetAllTeamNames() []string
	GetAllTeams() []Team
	GetAllOrgNames() []string
	GetAllOrgs() []Org
	GetAllPillarNames() []string
	GetAllPillars() []Pillar
	GetAllTeamGroupNames() []string
	GetAllTeamGroups() []TeamGroup

	// Hierarchy queries
	GetHierarchyPath(entityName string, entityType string) []HierarchyPathEntry
	GetDescendantsTree(entityName string) *HierarchyNode

	// Component queries
	GetComponentByName(name string) *Component
	GetAllComponents() []Component
	GetAllComponentNames() []string
	GetTeamsForComponent(componentName string) []ComponentOwnerInfo
	GetComponentsForTeam(teamName string) []ComponentOwnership

	// Jira queries
	GetJiraProjects() []string
	GetJiraComponents(project string) []string
	GetTeamsByJiraProject(project string) []JiraOwnerInfo
	GetTeamsByJiraComponent(project, component string) []JiraOwnerInfo
	GetJiraOwnershipForTeam(teamName string) []JiraOwnership

	// Context queries
	GetContextForTeam(teamName string) []ContextItemInfo
	GetContextForEntity(entityName string, entityType string) []ContextItemInfo
	GetContextByType(entityName string, contextType string, entityType string) []ContextItemInfo
	GetAllContextTypesForEntity(entityName string, entityType string) []string
	GetContextTypeDescriptions() map[string]string
}

type OrgInfo struct {
	Name     string      `json:"name"`
	Type     OrgInfoType `json:"type"`
	StableID string      `json:"stable_id,omitempty"`
}

type GCSConfig struct {
	Bucket          string        `json:"bucket"`
	ObjectPath      string        `json:"object_path"`
	ProjectID       string        `json:"project_id"`
	CredentialsJSON string        `json:"credentials_json"`
	CheckInterval   time.Duration `json:"check_interval"`
}
