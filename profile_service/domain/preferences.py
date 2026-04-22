from enum import StrEnum

import pydantic


class GenderPref(StrEnum):
    MALE = "male"
    FEMALE = "female"
    ANY = "any"


class Preferences(pydantic.BaseModel):
    profile_id: int = pydantic.Field(description="Profile ID")
    age_min: int | None = pydantic.Field(None, description="Minimum preferred age")
    age_max: int | None = pydantic.Field(None, description="Maximum preferred age")
    gender_pref: GenderPref | None = pydantic.Field(None, description="Gender preference")
    max_distance_km: int | None = pydantic.Field(None, description="Maximum distance in km")
