# -*- coding: utf-8 -*-
# Stub file — run `just generate-profile-api` to replace with real generated protobuf code.
# source: profile_api/v1/profile.proto
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    "",
    "profile_api/v1/profile.proto",
)

_sym_db = _symbol_database.Default()

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b"\n\x1cprofile_api/v1/profile.proto\x12\x0eprofile_api.v1\"\x0f\n\rHealthRequest\"\x1c\n\x0eHealthResponse\x12\n\n\x02ok\x18\x01 \x01(\x08\"o\n\x14\x43reateProfileRequest\x12\x13\n\x0btelegram_id\x18\x01 \x01(\x03\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x0b\n\x03\x61ge\x18\x03 \x01(\x05\x12\x0c\n\x04\x63ity\x18\x04 \x01(\t\x12\x0b\n\x03\x62io\x18\x05 \x01(\t\x12\"\n\x06gender\x18\x06 \x01(\x0e\x32\x12.profile_api.v1.Gender\")\n\x15\x43reateProfileResponse\x12\x10\n\nprofile_id\x18\x01 \x01(\x03\"$\n\x11GetProfileRequest\x12\x13\n\x0btelegram_id\x18\x01 \x01(\x03\"\xac\x01\n\x12GetProfileResponse\x12\r\n\x05\x66ound\x18\x01 \x01(\x08\x12\x12\n\nprofile_id\x18\x02 \x01(\x03\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x0b\n\x03\x61ge\x18\x04 \x01(\x05\x12\x0c\n\x04\x63ity\x18\x05 \x01(\t\x12\x0b\n\x03\x62io\x18\x06 \x01(\t\x12\"\n\x06gender\x18\x07 \x01(\x0e\x32\x12.profile_api.v1.Gender\x12)\n\x06photos\x18\x08 \x03(\x0b\x32\x19.profile_api.v1.PhotoInfo\"0\n\tPhotoInfo\x12\x10\n\x08photo_id\x18\x01 \x01(\x03\x12\x11\n\tis_active\x18\x02 \x01(\x08\"Y\n\x15UpdateProfileRequest\x12\x13\n\x0btelegram_id\x18\x01 \x01(\x03\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x0b\n\x03\x61ge\x18\x03 \x01(\x05\x12\x0c\n\x04\x63ity\x18\x04 \x01(\t\x12\x0b\n\x03\x62io\x18\x05 \x01(\t\")\n\x16UpdateProfileResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\"Z\n\x12UploadPhotoRequest\x12\x13\n\x0btelegram_id\x18\x01 \x01(\x03\x12\x0c\n\x04\x64\x61ta\x18\x02 \x01(\x0c\x12\x14\n\x0c\x63ontent_type\x18\x03 \x01(\t\"<\n\x13UploadPhotoResponse\x12\x10\n\x08photo_id\x18\x01 \x01(\x03\x12\x11\n\tminio_key\x18\x02 \x01(\t\")\n\x16GetPresignedUrlRequest\x12\x10\n\x08photo_id\x18\x01 \x01(\x03\"\"\n\x17GetPresignedUrlResponse\x12\x07\n\x03url\x18\x01 \x01(\t*F\n\x06Gender\x12\x16\n\x12GENDER_UNSPECIFIED\x10\x00\x12\x0f\n\x0bGENDER_MALE\x10\x01\x12\x13\n\x0fGENDER_FEMALE\x10\x02\x62\x06proto3"
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "profile_api.v1.profile_pb2", _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
