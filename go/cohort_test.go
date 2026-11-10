package orgdatacore

import (
	"encoding/json"
	"testing"
)

func TestGetCohortByName(t *testing.T) {
	service := NewService()
	service.data = &Data{
		Lookups: Lookups{
			Cohorts: map[string]Cohort{
				"HCM All": {
					UID:   "cohort1",
					Name:  "HCM All",
					Type:  "cohort",
					Group: Group{Type: GroupType{Name: "cohort"}},
				},
			},
		},
	}

	if got := service.GetCohortByName("HCM All"); got == nil || got.UID != "cohort1" {
		t.Errorf("expected cohort1, got %+v", got)
	}
	if got := service.GetCohortByName("Nonexistent"); got != nil {
		t.Errorf("expected nil, got %+v", got)
	}
}

func TestGetAllCohorts(t *testing.T) {
	service := NewService()
	service.data = &Data{
		Lookups: Lookups{
			Cohorts: map[string]Cohort{
				"A": {UID: "c1", Name: "A"},
				"B": {UID: "c2", Name: "B"},
			},
		},
	}
	if names := service.GetAllCohortNames(); len(names) != 2 {
		t.Errorf("expected 2 cohort names, got %d", len(names))
	}
	if cohorts := service.GetAllCohorts(); len(cohorts) != 2 {
		t.Errorf("expected 2 cohorts, got %d", len(cohorts))
	}
}

func TestGroupTypeVisualizeUnmarshal(t *testing.T) {
	var gt GroupType
	if err := json.Unmarshal([]byte(`{"name":"team","visualize":true,"visualize_group":["ocp","rosa"]}`), &gt); err != nil {
		t.Fatal(err)
	}
	if !gt.Visualize || len(gt.VisualizeGroup) != 2 || gt.VisualizeGroup[0] != "ocp" {
		t.Errorf("visualize not parsed: %+v", gt)
	}
}

func TestComponentVisualizeUnmarshal(t *testing.T) {
	var c Component
	raw := `{"name":"c","component":{"type":{"name":"system","visualize":true,"visualize_group":["ocp"]}}}`
	if err := json.Unmarshal([]byte(raw), &c); err != nil {
		t.Fatal(err)
	}
	if c.Type != "system" || !c.Visualize || len(c.VisualizeGroup) != 1 || c.VisualizeGroup[0] != "ocp" {
		t.Errorf("component visualize not parsed: %+v", c)
	}
}
