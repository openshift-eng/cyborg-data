package orgdatacore

import "testing"

func TestMembershipType(t *testing.T) {
	tests := []struct {
		mt      MembershipType
		str     string
		isValid bool
	}{
		{MembershipTeam, "team", true},
		{MembershipOrg, "org", true},
		{MembershipPillar, "pillar", true},
		{MembershipTeamGroup, "team_group", true},
		{MembershipType("invalid"), "invalid", false},
		{MembershipType(""), "", false},
	}

	for _, tt := range tests {
		t.Run(string(tt.mt), func(t *testing.T) {
			if got := tt.mt.String(); got != tt.str {
				t.Errorf("String() = %q, want %q", got, tt.str)
			}
			if got := tt.mt.IsValid(); got != tt.isValid {
				t.Errorf("IsValid() = %v, want %v", got, tt.isValid)
			}
		})
	}
}

func TestOrgInfoType(t *testing.T) {
	tests := []struct {
		ot      OrgInfoType
		str     string
		isValid bool
	}{
		{OrgTypeOrganization, "Organization", true},
		{OrgTypeTeam, "Team", true},
		{OrgTypePillar, "Pillar", true},
		{OrgTypeTeamGroup, "Team Group", true},
		{OrgTypeParentTeam, "Parent Team", true},
		{OrgInfoType("invalid"), "invalid", false},
		{OrgInfoType(""), "", false},
	}

	for _, tt := range tests {
		t.Run(string(tt.ot), func(t *testing.T) {
			if got := tt.ot.String(); got != tt.str {
				t.Errorf("String() = %q, want %q", got, tt.str)
			}
			if got := tt.ot.IsValid(); got != tt.isValid {
				t.Errorf("IsValid() = %v, want %v", got, tt.isValid)
			}
		})
	}
}

func TestEntityType(t *testing.T) {
	tests := []struct {
		et      EntityType
		str     string
		isValid bool
	}{
		{EntityEmployee, "employee", true},
		{EntityTeam, "team", true},
		{EntityOrg, "org", true},
		{EntityPillar, "pillar", true},
		{EntityTeamGroup, "team_group", true},
		{EntityType("invalid"), "invalid", false},
		{EntityType(""), "", false},
	}

	for _, tt := range tests {
		t.Run(string(tt.et), func(t *testing.T) {
			if got := tt.et.String(); got != tt.str {
				t.Errorf("String() = %q, want %q", got, tt.str)
			}
			if got := tt.et.IsValid(); got != tt.isValid {
				t.Errorf("IsValid() = %v, want %v", got, tt.isValid)
			}
		})
	}
}
