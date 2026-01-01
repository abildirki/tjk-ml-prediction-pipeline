from enum import Enum

class SurfaceType(str, Enum):
    CIM = "Çim"
    KUM = "Kum"
    SENTETIK = "Sentetik"
    UNKNOWN = "Unknown"

class Gender(str, Enum):
    MALE = "Erkek"
    FEMALE = "Dişi"
    GELDING = "İğdiş"
    UNKNOWN = "Unknown"
