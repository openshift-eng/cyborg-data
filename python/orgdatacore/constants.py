"""Constants for orgdatacore."""

from enum import StrEnum
from typing import Final


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


# Legacy constants for backwards compatibility (type-safe with Final)
MEMBERSHIP_TYPE_TEAM: Final = MembershipType.TEAM
MEMBERSHIP_TYPE_ORG: Final = MembershipType.ORG
ORG_INFO_TYPE_ORGANIZATION: Final = OrgInfoType.ORGANIZATION
ORG_INFO_TYPE_TEAM: Final = OrgInfoType.TEAM
ORG_INFO_TYPE_PILLAR: Final = OrgInfoType.PILLAR
ORG_INFO_TYPE_TEAM_GROUP: Final = OrgInfoType.TEAM_GROUP
ORG_INFO_TYPE_PARENT_TEAM: Final = OrgInfoType.PARENT_TEAM
