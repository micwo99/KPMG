from pydantic import BaseModel, Field, field_validator
from typing import Optional

class Date(BaseModel):
    day: str = ""
    month: str = ""
    year: str = ""

class Address(BaseModel):
    street: str = ""
    houseNumber: str = ""
    entrance: str = ""
    apartment: str = ""
    city: str = ""
    postalCode: str = ""
    poBox: str = ""

class MedicalInstitutionFields(BaseModel):
    healthFundMember: str = ""
    natureOfAccident: str = ""
    medicalDiagnoses: str = ""

class ExtractedForm(BaseModel):
    lastName: str = ""
    firstName: str = ""
    idNumber: str = ""
    gender: str = ""
    dateOfBirth: Date = Field(default_factory=Date)
    address: Address = Field(default_factory=Address)
    landlinePhone: str = ""
    mobilePhone: str = ""
    jobType: str = ""
    dateOfInjury: Date = Field(default_factory=Date)
    timeOfInjury: str = ""
    accidentLocation: str = ""
    accidentAddress: str = ""
    accidentDescription: str = ""
    injuredBodyPart: str = ""
    signature: str = ""
    formFillingDate: Date = Field(default_factory=Date)
    formReceiptDateAtClinic: Date = Field(default_factory=Date)
    medicalInstitutionFields: MedicalInstitutionFields = Field(default_factory=MedicalInstitutionFields)

    @field_validator("idNumber")
    @classmethod
    def id_must_be_9digits_or_empty(cls, v: str) -> str:
        vv = ''.join([c for c in v if c.isdigit()])
        if len(vv) == 9:
            return vv
        return v  # keep as-is; spec says empty string if unknown

    @field_validator("landlinePhone", "mobilePhone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        digits = ''.join([c for c in v if c.isdigit()])
        if digits:
            # Si le premier chiffre est 6, 8 ou 9, on le remplace par 0
            if digits[0] in {'6', '8', '9'}:
                digits = '0' + digits[1:]
        return digits or v
