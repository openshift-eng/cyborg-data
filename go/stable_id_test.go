package orgdatacore

import (
	"context"
	"encoding/json"
	"reflect"
	"testing"
)

// collisionData builds an index where a team and a team_group share the name
// "shared", disambiguated by stable IDs and linked by parent_id:
//
//	acme(org, o1) -> shared(team_group, g1) -> shared(team, t1) -> leaf(team, l1)
func collisionData() *Data {
	return &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Orgs:      map[string]Org{"acme": {Name: "acme", Type: "org", StableID: "o1"}},
			TeamGroups: map[string]TeamGroup{
				"shared": {Name: "shared", Type: "team_group", StableID: "g1", Parent: &ParentInfo{Name: "acme", Type: "org"}, ParentID: "o1"},
			},
			Teams: map[string]Team{
				"shared": {Name: "shared", Type: "team", StableID: "t1", Parent: &ParentInfo{Name: "shared", Type: "team_group"}, ParentID: "g1"},
				"leaf":   {Name: "leaf", Type: "team", StableID: "l1", Parent: &ParentInfo{Name: "shared", Type: "team"}, ParentID: "t1"},
			},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
				"euser": {{Name: "shared", Type: "team", StableID: "t1"}},
			}},
			SlackIDMappings: SlackIDMappings{SlackUIDToUID: map[string]string{"Suser": "euser"}},
		},
	}
}

func loadCollision(t *testing.T) *Service {
	t.Helper()
	b, err := json.Marshal(collisionData())
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	svc := NewService()
	if err := svc.LoadFromDataSource(context.Background(), NewFakeDataSource(string(b))); err != nil {
		t.Fatalf("load: %v", err)
	}
	if !svc.useStableIDs {
		t.Fatal("expected useStableIDs=true when stable ids present")
	}
	return svc
}

func TestHierarchyPathStableIDCollision(t *testing.T) {
	svc := loadCollision(t)

	// Explicit team_group request must resolve the team_group, not be rejected
	// because a team shares the name (the pre-stable-id Go bug returned empty).
	tg := svc.GetHierarchyPath("shared", "team_group")
	wantTG := []HierarchyPathEntry{
		{Name: "shared", Type: "team_group", StableID: "g1"},
		{Name: "acme", Type: "org", StableID: "o1"},
	}
	if !reflect.DeepEqual(tg, wantTG) {
		t.Errorf("team_group path = %+v, want %+v", tg, wantTG)
	}

	// Explicit team request ascends through the same-named team_group by id.
	team := svc.GetHierarchyPath("shared", "team")
	wantTeam := []HierarchyPathEntry{
		{Name: "shared", Type: "team", StableID: "t1"},
		{Name: "shared", Type: "team_group", StableID: "g1"},
		{Name: "acme", Type: "org", StableID: "o1"},
	}
	if !reflect.DeepEqual(team, wantTeam) {
		t.Errorf("team path = %+v, want %+v", team, wantTeam)
	}
}

func TestDescendantsTreeStableIDCollision(t *testing.T) {
	svc := loadCollision(t)
	tree := svc.GetDescendantsTree("acme")
	if tree == nil {
		t.Fatal("nil tree")
	}
	// acme -> shared(team_group) -> shared(team) -> leaf(team); the same-named
	// nodes must remain distinct (name-only keying would merge/short-circuit).
	if len(tree.Children) != 1 || tree.Children[0].Type != "team_group" || tree.Children[0].StableID != "g1" {
		t.Fatalf("acme child = %+v, want shared/team_group/g1", tree.Children)
	}
	tg := tree.Children[0]
	if len(tg.Children) != 1 || tg.Children[0].Type != "team" || tg.Children[0].StableID != "t1" {
		t.Fatalf("team_group child = %+v, want shared/team/t1", tg.Children)
	}
	team := tg.Children[0]
	if len(team.Children) != 1 || team.Children[0].Name != "leaf" {
		t.Fatalf("team child = %+v, want leaf", team.Children)
	}
}

func TestUserOrganizationsStableIDCollision(t *testing.T) {
	svc := loadCollision(t)
	got := svc.GetUserOrganizations("Suser")

	// euser is in team shared -> team_group shared -> org acme. All three appear
	// with distinct types and stable ids; deduping by name alone would drop the
	// team_group.
	want := []OrgInfo{
		{Name: "shared", Type: OrgTypeTeam, StableID: "t1"},
		{Name: "shared", Type: OrgTypeTeamGroup, StableID: "g1"},
		{Name: "acme", Type: OrgTypeOrganization, StableID: "o1"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("GetUserOrganizations = %+v, want %+v", got, want)
	}

	if !svc.IsEmployeeInOrg("euser", "acme") {
		t.Error("expected euser in org acme via stable-id hierarchy")
	}
}

// TestBackwardCompatNoStableIDs verifies that an index without stable ids uses
// the legacy name+type traversal and still resolves a simple hierarchy.
func TestBackwardCompatNoStableIDs(t *testing.T) {
	data := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Orgs:      map[string]Org{"acme": {Name: "acme", Type: "org"}},
			TeamGroups: map[string]TeamGroup{
				"grp": {Name: "grp", Type: "team_group", Parent: &ParentInfo{Name: "acme", Type: "org"}},
			},
			Teams: map[string]Team{
				"t": {Name: "t", Type: "team", Parent: &ParentInfo{Name: "grp", Type: "team_group"}},
			},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
				"euser": {{Name: "t", Type: "team"}},
			}},
		},
	}
	b, err := json.Marshal(data)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	svc := NewService()
	if err := svc.LoadFromDataSource(context.Background(), NewFakeDataSource(string(b))); err != nil {
		t.Fatalf("load: %v", err)
	}
	if svc.useStableIDs {
		t.Fatal("expected useStableIDs=false for index without stable ids")
	}
	path := svc.GetHierarchyPath("t", "team")
	want := []HierarchyPathEntry{
		{Name: "t", Type: "team"},
		{Name: "grp", Type: "team_group"},
		{Name: "acme", Type: "org"},
	}
	if !reflect.DeepEqual(path, want) {
		t.Errorf("fallback path = %+v, want %+v", path, want)
	}
}

// TestUserOrgsAncestryOrderingAndCycles covers the stable-ID ancestor walk:
// a direct org membership listed before a team under it must not truncate the
// team's higher ancestors, and cyclic parent links must terminate.
func TestUserOrgsAncestryOrderingAndCycles(t *testing.T) {
	// P(org) <- O(org) <- T(team); membership lists O (direct) before T.
	ordering := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Orgs: map[string]Org{
				"P": {Name: "P", Type: "org", StableID: "p1"},
				"O": {Name: "O", Type: "org", StableID: "o1", Parent: &ParentInfo{Name: "P", Type: "org"}, ParentID: "p1"},
			},
			Teams: map[string]Team{
				"T": {Name: "T", Type: "team", StableID: "t1", Parent: &ParentInfo{Name: "O", Type: "org"}, ParentID: "o1"},
			},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
				"euser": {
					{Name: "O", Type: "org", StableID: "o1"},
					{Name: "T", Type: "team", StableID: "t1"},
				},
			}},
			SlackIDMappings: SlackIDMappings{SlackUIDToUID: map[string]string{"Suser": "euser"}},
		},
	}
	svc := loadData(t, ordering)
	got := map[string]OrgInfoType{}
	for _, o := range svc.GetUserOrganizations("Suser") {
		got[o.Name] = o.Type
	}
	if got["P"] != OrgTypeOrganization {
		t.Errorf("expected P/Organization retained despite O seen first; got %+v", got)
	}
	if got["O"] != OrgTypeOrganization || got["T"] != OrgTypeTeam {
		t.Errorf("expected O and T present; got %+v", got)
	}

	// Cyclic parents A <-> B, team T under A. Must terminate and include members.
	cycle := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Orgs: map[string]Org{
				"A": {Name: "A", Type: "org", StableID: "a1", Parent: &ParentInfo{Name: "B", Type: "org"}, ParentID: "b1"},
				"B": {Name: "B", Type: "org", StableID: "b1", Parent: &ParentInfo{Name: "A", Type: "org"}, ParentID: "a1"},
			},
			Teams: map[string]Team{
				"T": {Name: "T", Type: "team", StableID: "t1", Parent: &ParentInfo{Name: "A", Type: "org"}, ParentID: "a1"},
			},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
				"euser": {{Name: "T", Type: "team", StableID: "t1"}},
			}},
			SlackIDMappings: SlackIDMappings{SlackUIDToUID: map[string]string{"Suser": "euser"}},
		},
	}
	svc2 := loadData(t, cycle)
	names := map[string]bool{}
	for _, o := range svc2.GetUserOrganizations("Suser") {
		names[o.Name] = true
	}
	for _, n := range []string{"T", "A", "B"} {
		if !names[n] {
			t.Errorf("expected %s in result (cycle must terminate and include members); got %+v", n, names)
		}
	}
}

// loadData marshals and loads a *Data through the real service load path.
func loadData(t *testing.T, d *Data) *Service {
	t.Helper()
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	svc := NewService()
	if err := svc.LoadFromDataSource(context.Background(), NewFakeDataSource(string(b))); err != nil {
		t.Fatalf("load: %v", err)
	}
	return svc
}

// TestLegacyUnknownParentTypeSkipped verifies that a legacy (no stable id)
// hierarchy whose parent carries an unknown/empty type does not blow up
// GetUserOrganizations; the unknown ancestor is skipped and the team remains.
func TestLegacyUnknownParentTypeSkipped(t *testing.T) {
	data := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Teams: map[string]Team{
				"t": {Name: "t", Type: "team", Parent: &ParentInfo{Name: "weird", Type: "bogus"}},
			},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
				"euser": {{Name: "t", Type: "team"}},
			}},
			SlackIDMappings: SlackIDMappings{SlackUIDToUID: map[string]string{"Suser": "euser"}},
		},
	}
	b, err := json.Marshal(data)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	svc := NewService()
	if err := svc.LoadFromDataSource(context.Background(), NewFakeDataSource(string(b))); err != nil {
		t.Fatalf("load: %v", err)
	}
	if svc.useStableIDs {
		t.Fatal("expected legacy mode")
	}
	got := svc.GetUserOrganizations("Suser")
	want := []OrgInfo{{Name: "t", Type: OrgTypeTeam}}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("GetUserOrganizations = %+v, want %+v", got, want)
	}
}

// TestMalformedStableIndexFallsBack verifies that defects in the identity graph
// (duplicate stable IDs, or a parent_id that resolves to nothing) disable stable
// traversal and fall back to legacy name+type resolution instead of silently
// returning wrong ancestry.
func TestMalformedStableIndexFallsBack(t *testing.T) {
	load := func(t *testing.T, d *Data) *Service {
		b, err := json.Marshal(d)
		if err != nil {
			t.Fatalf("marshal: %v", err)
		}
		svc := NewService()
		if err := svc.LoadFromDataSource(context.Background(), NewFakeDataSource(string(b))); err != nil {
			t.Fatalf("load: %v", err)
		}
		return svc
	}
	membership := Indexes{Membership: MembershipIndex{MembershipIndex: map[string][]MembershipInfo{
		"euser": {{Name: "t", Type: "team"}},
	}}}

	// Duplicate stable IDs across a team and an org.
	dup := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Orgs:      map[string]Org{"acme": {Name: "acme", Type: "org", StableID: "dupe"}},
			Teams:     map[string]Team{"t": {Name: "t", Type: "team", StableID: "dupe"}},
		},
		Indexes: membership,
	}
	if load(t, dup).useStableIDs {
		t.Error("duplicate stable IDs should disable stable traversal")
	}

	// parent_id pointing to a non-existent entity.
	dangling := &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{"euser": {UID: "euser"}},
			Teams: map[string]Team{
				"t": {Name: "t", Type: "team", StableID: "t1", Parent: &ParentInfo{Name: "ghost", Type: "org"}, ParentID: "missing"},
			},
		},
		Indexes: membership,
	}
	if load(t, dangling).useStableIDs {
		t.Error("unresolved parent_id should disable stable traversal")
	}
}
