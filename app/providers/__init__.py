# These are retriable exceptions that might get raised by calls to AWS SNS.Client.publish.
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
sns_publish_retriable_exceptions_set = {
    'InternalErrorException',
    'EndpointDisabledException',
    'PlatformApplicationDisabledException',
    'KMSDisabledException',
    'KMSInvalidStateException',
    'KMSThrottlingException',
}
