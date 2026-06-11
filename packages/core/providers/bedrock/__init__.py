"""AWS provider namespace — interface-complete stubs (v1; not wired).

This package is the AWS backend namespace for the platform's three cloud-variant seams:
  - ``llm`` → Amazon Bedrock (``BedrockLLMProvider``)
  - ``transcription`` → Amazon Transcribe (``BedrockTranscriptionProvider``)
  - ``storage`` → Amazon S3 (``BedrockObjectStorage``)

Every class satisfies its ``core.interfaces`` ABC and is instantiable; method bodies raise
``NotImplementedError`` loudly (see ``core.providers._not_wired``). No cloud SDK (boto3/botocore/
amazon_transcribe) is imported until a body is actually filled in.

NAMESPACE NOTE (intentional, deferred rename): this package is named ``bedrock`` after the AWS
*cloud profile* selected by config (``provider: bedrock``/``aws``), not after the Bedrock LLM
service specifically. It is the single AWS namespace covering all three seams — Bedrock (LLM),
Transcribe (STT), and S3 (storage). The class names keep the ``Bedrock``/``S3`` prefixes for now;
renaming to fully service-accurate names (e.g. ``AWSTranscribeProvider``) is deferred until AWS is
actually wired, to avoid churn on code that is still a stub. The config keys, not the class names,
are the stable contract.
"""
