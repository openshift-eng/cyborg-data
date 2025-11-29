//go:build go1.23

package orgdatacore

import "iter"

func (s *Service) AllEmployeeUIDs() iter.Seq[string] {
	return func(yield func(string) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Employees == nil {
			return
		}

		for uid := range s.data.Lookups.Employees {
			if !yield(uid) {
				return
			}
		}
	}
}

func (s *Service) AllEmployees() iter.Seq[*Employee] {
	return func(yield func(*Employee) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Employees == nil {
			return
		}

		for _, emp := range s.data.Lookups.Employees {
			e := emp
			if !yield(&e) {
				return
			}
		}
	}
}

func (s *Service) AllTeamNames() iter.Seq[string] {
	return func(yield func(string) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Teams == nil {
			return
		}

		for name := range s.data.Lookups.Teams {
			if !yield(name) {
				return
			}
		}
	}
}

func (s *Service) AllTeams() iter.Seq2[string, *Team] {
	return func(yield func(string, *Team) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Teams == nil {
			return
		}

		for name, team := range s.data.Lookups.Teams {
			t := team
			if !yield(name, &t) {
				return
			}
		}
	}
}

func (s *Service) AllOrgNames() iter.Seq[string] {
	return func(yield func(string) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Orgs == nil {
			return
		}

		for name := range s.data.Lookups.Orgs {
			if !yield(name) {
				return
			}
		}
	}
}

func (s *Service) AllOrgs() iter.Seq2[string, *Org] {
	return func(yield func(string, *Org) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Orgs == nil {
			return
		}

		for name, org := range s.data.Lookups.Orgs {
			o := org
			if !yield(name, &o) {
				return
			}
		}
	}
}

func (s *Service) AllPillarNames() iter.Seq[string] {
	return func(yield func(string) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Pillars == nil {
			return
		}

		for name := range s.data.Lookups.Pillars {
			if !yield(name) {
				return
			}
		}
	}
}

func (s *Service) AllPillars() iter.Seq2[string, *Pillar] {
	return func(yield func(string, *Pillar) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.Pillars == nil {
			return
		}

		for name, pillar := range s.data.Lookups.Pillars {
			p := pillar
			if !yield(name, &p) {
				return
			}
		}
	}
}

func (s *Service) AllTeamGroupNames() iter.Seq[string] {
	return func(yield func(string) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.TeamGroups == nil {
			return
		}

		for name := range s.data.Lookups.TeamGroups {
			if !yield(name) {
				return
			}
		}
	}
}

func (s *Service) AllTeamGroups() iter.Seq2[string, *TeamGroup] {
	return func(yield func(string, *TeamGroup) bool) {
		s.mu.RLock()
		defer s.mu.RUnlock()

		if s.data == nil || s.data.Lookups.TeamGroups == nil {
			return
		}

		for name, tg := range s.data.Lookups.TeamGroups {
			teamGroup := tg
			if !yield(name, &teamGroup) {
				return
			}
		}
	}
}
