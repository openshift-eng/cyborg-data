"""Constants for orgdatacore."""

from enum import StrEnum


class MembershipType(StrEnum):
    """Membership types for organizational hierarchy."""
    TEAM = "team"
    ORG = "org"


class OrgInfoType(StrEnum):
    """Organization info types returned by get_user_organizations."""
    ORGANIZATION = "Organization"
    TEAM = "Team"
    PILLAR = "Pillar"
    TEAM_GROUP = "Team Group"
    PARENT_TEAM = "Parent Team"


# Legacy constants for backwards compatibility
MEMBERSHIP_TYPE_TEAM = MembershipType.TEAM
MEMBERSHIP_TYPE_ORG = MembershipType.ORG
ORG_INFO_TYPE_ORGANIZATION = OrgInfoType.ORGANIZATION
ORG_INFO_TYPE_TEAM = OrgInfoType.TEAM
ORG_INFO_TYPE_PILLAR = OrgInfoType.PILLAR
ORG_INFO_TYPE_TEAM_GROUP = OrgInfoType.TEAM_GROUP
ORG_INFO_TYPE_PARENT_TEAM = OrgInfoType.PARENT_TEAM
