# Thse are the keyword arguments needed to instantiate various botocore exceptions.
botocore_exceptions_kwargs = {
    'DataNotFoundError': ('data_path',),
    'UnknownServiceError': ('service_name', 'known_service_names'),
    'UnknownRegionError': ('region_name', 'error_msg'),
    'ApiVersionNotFoundError': ('data_path', 'api_version'),
    'HTTPClientError': ('error',),
    'ConnectionError': ('error',),
    'ResponseStreamingError': ('error',),
    'InvalidIMDSEndpointError': ('endpoint',),
    'InvalidIMDSEndpointModeError': ('mode', 'valid_modes'),
    'EndpointConnectionError': ('endpoint_url',),
    'ConnectionClosedError': ('endpoint_url',),
    'ReadTimeoutError': ('endpoint_url',),
    'ConnectTimeoutError': ('endpoint_url',),
    'SSLError': ('endpoint_url', 'error'),
    'ProxyConnectionError': ('proxy_url',),
    'TokenRetrievalError': ('provider', 'error_msg'),
    'CredentialRetrievalError': ('provider', 'error_msg'),
    'PartialCredentialsError': ('provider', 'cred_var'),
    'UnknownSignatureVersionError': ('signature_version',),
    'UnsupportedSignatureVersionError': ('signature_version',),
    'ServiceNotInRegionError': ('service_name', 'region_name'),
    'UnknownEndpointError': ('service_name', 'region_name'),
    'EndpointVariantError': ('tags',),
    'UnknownFIPSEndpointError': ('region_name', 'service_name'),
    'ProfileNotFound': ('profile',),
    'ConfigParseError': ('path',),
    'ConfigNotFound': ('path',),
    'MissingParametersError': ('object_name', 'missing'),
    'ValidationError': ('value', 'param', 'type_name'),
    'ParamValidationError': ('report',),
    'UnknownKeyError': ('value', 'param', 'choices'),
    'RangeError': ('param', 'min_value', 'value', 'max_value'),
    'UnknownParameterError': ('name', 'operation', 'choices'),
    'InvalidRegionError': ('region_name',),
    'AliasConflictParameterError': ('original', 'alias', 'operation'),
    'UnknownServiceStyle': ('service_style',),
    'PaginationError': ('message',),
    'OperationNotPageableError': ('operation_name',),
    'ChecksumError': ('checksum_type', 'expected_checksum', 'actual_checksum'),
    'InvalidChecksumConfigError': ('config_key', 'valid_options', 'config_value'),
    'UnseekableStreamError': ('stream_object',),
    'IncompleteReadError': ('actual_bytes', 'expected_bytes'),
    'InvalidExpressionError': ('expression',),
    'UnknownCredentialError': ('name',),
    'UnknownEndpointResolutionBuiltInName': ('name',),
    'WaiterConfigError': ('error_msg',),
    'InvalidConfigError': ('error_msg',),
    'MetadataRetrievalError': ('error_msg',),
    'SSOTokenLoadError': ('error_msg',),
    'AwsChunkedWrapperError': ('error_msg',),
    'FlexibleChecksumError': ('error_msg',),
    'UnknownClientMethodError': ('method_name',),
    'InvalidDNSNameError': ('bucket_name',),
    'InvalidS3AddressingStyleError': ('s3_addressing_style',),
    'UnsupportedS3ArnError': ('arn',),
    'UnsupportedS3ControlArnError': ('arn', 'msg'),
    'InvalidHostLabelError': ('label',),
    'UnsupportedOutpostResourceError': ('resource_name',),
    'UnsupportedS3ConfigurationError': ('msg',),
    'UnsupportedS3AccesspointConfigurationError': ('msg',),
    'UnsupportedS3ControlConfigurationError': ('msg',),
    'MissingDependencyException': ('msg',),
    'InvalidEndpointConfigurationError': ('msg',),
    'EndpointProviderError': ('msg',),
    'EndpointResolutionError': ('msg',),
    'InvalidEndpointDiscoveryConfigurationError': ('config_value',),
    'InvalidRetryConfigurationError': ('retry_config_option', 'valid_options'),
    'InvalidMaxRetryAttemptsError': ('provided_max_attempts', 'min_value'),
    'InvalidRetryModeError': ('provided_retry_mode', 'valid_modes'),
    'InvalidS3UsEast1RegionalEndpointConfigError': ('s3_us_east_1_regional_endpoint_config',),
    'InvalidSTSRegionalEndpointsConfigError': ('sts_regional_endpoints_config',),
    'StubResponseError': ('operation_name', 'reason'),
    'StubAssertionError': ('operation_name', 'reason'),
    'UnStubbedResponseError': ('operation_name', 'reason'),
    'InfiniteLoopConfigError': ('source_profile', 'visited_profiles'),
    'MissingServiceIdError': ('service_name',),
    'InvalidDefaultsMode': ('mode', 'valid_modes'),
    'UnsupportedServiceProtocolsError': ('botocore_supported_protocols', 'service', 'service_supported_protocols'),
}
