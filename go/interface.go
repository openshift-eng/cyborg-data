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

type ServiceInterface interface {
	GetEmployeeByUID(uid string) *Employee
	GetEmployeeBySlackID(slackID string) *Employee
	GetEmployeeByGitHubID(githubID string) *Employee
	GetEmployeeByEmail(email string) *Employee
	GetManagerForEmployee(uid string) *Employee
	GetTeamByName(teamName string) *Team
	GetOrgByName(orgName string) *Org
	GetPillarByName(pillarName string) *Pillar
	GetTeamGroupByName(teamGroupName string) *TeamGroup

	GetTeamsForUID(uid string) []string
	GetTeamsForSlackID(slackID string) []string
	GetTeamMembers(teamName string) []Employee
	IsEmployeeInTeam(uid string, teamName string) bool
	IsSlackUserInTeam(slackID string, teamName string) bool

	IsEmployeeInOrg(uid string, orgName string) bool
	IsSlackUserInOrg(slackID string, orgName string) bool
	GetUserOrganizations(slackUserID string) []OrgInfo

	GetVersion() DataVersion
	LoadFromDataSource(ctx context.Context, source DataSource) error
	StartDataSourceWatcher(ctx context.Context, source DataSource) error

	GetAllEmployeeUIDs() []string
	GetAllTeamNames() []string
	GetAllOrgNames() []string
	GetAllPillarNames() []string
	GetAllTeamGroupNames() []string
}

type OrgInfo struct {
	Name string      `json:"name"`
	Type OrgInfoType `json:"type"`
}

type GCSConfig struct {
	Bucket          string        `json:"bucket"`
	ObjectPath      string        `json:"object_path"`
	ProjectID       string        `json:"project_id"`
	CredentialsJSON string        `json:"credentials_json"`
	CheckInterval   time.Duration `json:"check_interval"`
}
