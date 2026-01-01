from pydantic import BaseModel, ConfigDict

class TJKBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra='ignore'
    )
