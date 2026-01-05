// API Parity Test Runner for Go implementation.
// Accepts method configuration via stdin for dynamic testing.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"reflect"
	"sort"

	orgdatacore "github.com/openshift-eng/cyborg-data/go"
)

// RunConfig is the configuration passed via stdin.
type RunConfig struct {
	TestDataPath string       `json:"test_data_path"`
	Methods      []MethodSpec `json:"methods"`
}

// MethodSpec describes a method to test.
type MethodSpec struct {
	GoName    string     `json:"go_name"`
	TestCases []TestCase `json:"test_cases"`
}

// TestCase is a single test case with named inputs.
type TestCase struct {
	Name   string                 `json:"name"`
	Inputs map[string]interface{} `json:"inputs"`
}

// TestResult is the output for a single test case.
type TestResult struct {
	MethodGoName string      `json:"method_go_name"`
	CaseName     string      `json:"case_name"`
	Output       interface{} `json:"output"`
	Error        string      `json:"error,omitempty"`
}

func main() {
	var config RunConfig
	if err := json.NewDecoder(os.Stdin).Decode(&config); err != nil {
		fmt.Fprintf(os.Stderr, "Error reading config: %v\n", err)
		os.Exit(2)
	}

	svc, err := loadService(config.TestDataPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading service: %v\n", err)
		os.Exit(2)
	}

	results := []TestResult{}
	for _, method := range config.Methods {
		for _, tc := range method.TestCases {
			results = append(results, runTestCase(svc, method.GoName, tc))
		}
	}

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(results); err != nil {
		fmt.Fprintf(os.Stderr, "Error encoding results: %v\n", err)
		os.Exit(2)
	}
}

func loadService(testDataPath string) (*orgdatacore.Service, error) {
	svc := orgdatacore.NewService()
	source := &fileDataSource{path: testDataPath}
	if err := svc.LoadFromDataSource(context.Background(), source); err != nil {
		return nil, err
	}
	return svc, nil
}

type fileDataSource struct {
	path string
}

func (f *fileDataSource) Load(_ context.Context) (io.ReadCloser, error) {
	return os.Open(f.path)
}

func (f *fileDataSource) Watch(_ context.Context, _ func() error) error {
	return nil
}

func (f *fileDataSource) String() string {
	return f.path
}

func (f *fileDataSource) Close() error {
	return nil
}

func runTestCase(svc *orgdatacore.Service, goName string, tc TestCase) TestResult {
	result := TestResult{
		MethodGoName: goName,
		CaseName:     tc.Name,
	}

	svcValue := reflect.ValueOf(svc)
	methodValue := svcValue.MethodByName(goName)
	if !methodValue.IsValid() {
		result.Error = fmt.Sprintf("method %s not found", goName)
		return result
	}

	args, err := buildArgs(goName, methodValue.Type(), tc.Inputs)
	if err != nil {
		result.Error = err.Error()
		return result
	}

	returnValues := methodValue.Call(args)
	if len(returnValues) > 0 {
		result.Output = serializeOutput(returnValues[0].Interface())
	}

	return result
}

func buildArgs(methodName string, methodType reflect.Type, inputs map[string]interface{}) ([]reflect.Value, error) {
	numParams := methodType.NumIn()
	args := make([]reflect.Value, numParams)
	paramNames := inferParamNames(methodName, methodType)

	for i := 0; i < numParams; i++ {
		paramType := methodType.In(i)
		paramName := ""
		if i < len(paramNames) {
			paramName = paramNames[i]
		}

		var input interface{}
		var found bool

		if paramName != "" {
			input, found = inputs[paramName]
		}

		if !found && len(inputs) == 1 {
			for _, v := range inputs {
				input = v
				found = true
				break
			}
		}

		if !found {
			for key, val := range inputs {
				if matchesParamName(key, paramName, paramType) {
					input = val
					found = true
					break
				}
			}
		}

		if !found {
			return nil, fmt.Errorf("missing input for parameter %d (%s)", i, paramName)
		}

		argValue, err := convertToType(input, paramType)
		if err != nil {
			return nil, fmt.Errorf("failed to convert arg %d: %v", i, err)
		}
		args[i] = argValue
	}

	return args, nil
}

// methodParamNames maps Go methods to parameter names (in Python snake_case).
// Required because Go reflection doesn't expose parameter names.
var methodParamNames = map[string][]string{
	"GetEmployeeByUID":       {"uid"},
	"GetEmployeeBySlackID":   {"slack_id"},
	"GetEmployeeByGitHubID":  {"github_id"},
	"GetEmployeeByEmail":     {"email"},
	"GetManagerForEmployee":  {"uid"},
	"GetTeamByName":          {"team_name"},
	"GetOrgByName":           {"org_name"},
	"GetPillarByName":        {"pillar_name"},
	"GetTeamGroupByName":     {"team_group_name"},
	"GetTeamsForUID":         {"uid"},
	"GetTeamsForSlackID":     {"slack_id"},
	"GetTeamMembers":         {"team_name"},
	"GetUserOrganizations":   {"slack_id"},
	"GetDescendantsTree":     {"name"},
	"GetComponentByName":     {"name"},
	"GetJiraComponents":      {"project"},
	"GetTeamsByJiraProject":  {"project"},
	"GetJiraOwnershipForTeam": {"team_name"},
	"IsEmployeeInTeam":       {"uid", "team_name"},
	"IsSlackUserInTeam":      {"slack_id", "team_name"},
	"IsEmployeeInOrg":        {"uid", "org_name"},
	"IsSlackUserInOrg":       {"slack_id", "org_name"},
	"GetHierarchyPath":       {"name", "entity_type"},
	"GetTeamsByJiraComponent": {"project", "component"},
}

func inferParamNames(methodName string, methodType reflect.Type) []string {
	if names, ok := methodParamNames[methodName]; ok {
		return names
	}

	names := []string{}
	for i := 0; i < methodType.NumIn(); i++ {
		if methodType.In(i).Kind() == reflect.String && i == 0 {
			names = append(names, "uid")
		} else {
			names = append(names, fmt.Sprintf("param%d", i))
		}
	}
	return names
}

func matchesParamName(inputKey, paramName string, paramType reflect.Type) bool {
	if inputKey == paramName {
		return true
	}

	mappings := map[string][]string{
		"uid":       {"uid", "employee_uid"},
		"slackID":   {"slack_id", "slackID"},
		"githubID":  {"github_id", "githubID"},
		"teamName":  {"team_name", "teamName", "team"},
		"orgName":   {"org_name", "orgName", "org"},
		"pillarName": {"pillar_name", "pillarName", "pillar"},
		"name":      {"name", "entity_name"},
		"email":     {"email"},
		"project":   {"project", "jira_project"},
		"component": {"component", "jira_component"},
	}

	for goName, pythonNames := range mappings {
		if paramName == goName {
			for _, pn := range pythonNames {
				if inputKey == pn {
					return true
				}
			}
		}
	}

	return false
}

func convertToType(input interface{}, targetType reflect.Type) (reflect.Value, error) {
	switch targetType.Kind() {
	case reflect.String:
		if s, ok := input.(string); ok {
			return reflect.ValueOf(s), nil
		}
		return reflect.Value{}, fmt.Errorf("expected string, got %T", input)
	case reflect.Int, reflect.Int64:
		if f, ok := input.(float64); ok {
			return reflect.ValueOf(int(f)), nil
		}
		return reflect.Value{}, fmt.Errorf("expected number, got %T", input)
	case reflect.Bool:
		if b, ok := input.(bool); ok {
			return reflect.ValueOf(b), nil
		}
		return reflect.Value{}, fmt.Errorf("expected bool, got %T", input)
	default:
		return reflect.Value{}, fmt.Errorf("unsupported type: %s", targetType.Kind())
	}
}

func serializeOutput(output interface{}) interface{} {
	if output == nil {
		return nil
	}

	v := reflect.ValueOf(output)
	if v.Kind() == reflect.Ptr && v.IsNil() {
		return nil
	}

	switch val := output.(type) {
	case bool:
		return val
	case string:
		return val
	case []string:
		return serializeStringList(val)
	case *orgdatacore.Employee:
		return serializeEmployee(val)
	case []orgdatacore.Employee:
		return serializeEmployeeList(val)
	case *orgdatacore.Team:
		return serializeTeam(val)
	case *orgdatacore.Org:
		return serializeOrg(val)
	case *orgdatacore.Pillar:
		return serializePillar(val)
	case *orgdatacore.TeamGroup:
		return serializeTeamGroup(val)
	case *orgdatacore.Component:
		return serializeComponent(val)
	case []orgdatacore.Component:
		return serializeComponentList(val)
	case []orgdatacore.HierarchyPathEntry:
		return serializeHierarchyPath(val)
	case *orgdatacore.HierarchyNode:
		return serializeHierarchyNode(val)
	case []orgdatacore.OrgInfo:
		return serializeOrgInfoList(val)
	case []orgdatacore.JiraOwnerInfo:
		return serializeJiraOwnerList(val)
	case []orgdatacore.JiraOwnership:
		return serializeJiraOwnershipList(val)
	default:
		return output
	}
}

func serializeStringList(v []string) interface{} {
	sorted := make([]string, len(v))
	copy(sorted, v)
	sort.Strings(sorted)
	return sorted
}

func serializeEmployee(emp *orgdatacore.Employee) interface{} {
	if emp == nil {
		return nil
	}
	return map[string]interface{}{
		"uid":       emp.UID,
		"full_name": emp.FullName,
		"email":     emp.Email,
	}
}

func serializeEmployeeList(emps []orgdatacore.Employee) interface{} {
	result := make([]map[string]interface{}, len(emps))
	for i, emp := range emps {
		result[i] = map[string]interface{}{
			"uid":       emp.UID,
			"full_name": emp.FullName,
			"email":     emp.Email,
		}
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i]["uid"].(string) < result[j]["uid"].(string)
	})
	return result
}

func serializeTeam(team *orgdatacore.Team) interface{} {
	if team == nil {
		return nil
	}
	return map[string]interface{}{
		"uid":         team.UID,
		"name":        team.Name,
		"description": team.Description,
	}
}

func serializeOrg(org *orgdatacore.Org) interface{} {
	if org == nil {
		return nil
	}
	return map[string]interface{}{
		"uid":         org.UID,
		"name":        org.Name,
		"description": org.Description,
	}
}

func serializePillar(pillar *orgdatacore.Pillar) interface{} {
	if pillar == nil {
		return nil
	}
	return map[string]interface{}{
		"uid":         pillar.UID,
		"name":        pillar.Name,
		"description": pillar.Description,
	}
}

func serializeTeamGroup(tg *orgdatacore.TeamGroup) interface{} {
	if tg == nil {
		return nil
	}
	return map[string]interface{}{
		"uid":         tg.UID,
		"name":        tg.Name,
		"description": tg.Description,
	}
}

func serializeComponent(comp *orgdatacore.Component) interface{} {
	if comp == nil {
		return nil
	}
	return map[string]interface{}{
		"name":        comp.Name,
		"description": comp.Description,
	}
}

func serializeComponentList(comps []orgdatacore.Component) interface{} {
	result := make([]map[string]interface{}, len(comps))
	for i, comp := range comps {
		result[i] = map[string]interface{}{
			"name":        comp.Name,
			"description": comp.Description,
		}
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i]["name"].(string) < result[j]["name"].(string)
	})
	return result
}

func serializeHierarchyPath(path []orgdatacore.HierarchyPathEntry) interface{} {
	result := make([]map[string]interface{}, len(path))
	for i, entry := range path {
		result[i] = map[string]interface{}{
			"name": entry.Name,
			"type": entry.Type,
		}
	}
	return result
}

func serializeHierarchyNode(node *orgdatacore.HierarchyNode) interface{} {
	if node == nil {
		return nil
	}
	return serializeNodeRecursive(node)
}

func serializeNodeRecursive(node *orgdatacore.HierarchyNode) map[string]interface{} {
	children := make([]map[string]interface{}, len(node.Children))
	for i := range node.Children {
		children[i] = serializeNodeRecursive(&node.Children[i])
	}
	sort.Slice(children, func(i, j int) bool {
		return children[i]["name"].(string) < children[j]["name"].(string)
	})
	return map[string]interface{}{
		"name":     node.Name,
		"type":     node.Type,
		"children": children,
	}
}

func serializeOrgInfoList(infos []orgdatacore.OrgInfo) interface{} {
	result := make([]map[string]interface{}, len(infos))
	for i, info := range infos {
		result[i] = map[string]interface{}{
			"name": info.Name,
			"type": string(info.Type),
		}
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i]["name"].(string) < result[j]["name"].(string)
	})
	return result
}

func serializeJiraOwnerList(owners []orgdatacore.JiraOwnerInfo) interface{} {
	result := make([]map[string]interface{}, len(owners))
	for i, owner := range owners {
		result[i] = map[string]interface{}{
			"name": owner.Name,
			"type": owner.Type,
		}
	}
	sort.Slice(result, func(i, j int) bool {
		return result[i]["name"].(string) < result[j]["name"].(string)
	})
	return result
}

func serializeJiraOwnershipList(ownerships []orgdatacore.JiraOwnership) interface{} {
	result := make([]map[string]interface{}, len(ownerships))
	for i, ownership := range ownerships {
		result[i] = map[string]interface{}{
			"project":   ownership.Project,
			"component": ownership.Component,
		}
	}
	sort.Slice(result, func(i, j int) bool {
		if result[i]["project"].(string) != result[j]["project"].(string) {
			return result[i]["project"].(string) < result[j]["project"].(string)
		}
		return result[i]["component"].(string) < result[j]["component"].(string)
	})
	return result
}
