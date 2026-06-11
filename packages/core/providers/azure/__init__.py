"""Azure provider namespace — interface-complete stubs (v1; not wired).

This package is the Azure backend namespace for the platform's three cloud-variant seams:
  - ``llm`` → Azure OpenAI (``AzureLLMProvider``)
  - ``transcription`` → Azure AI Speech (``AzureTranscriptionProvider``)
  - ``storage`` → Azure Blob Storage (``AzureObjectStorage``)

Every class satisfies its ``core.interfaces`` ABC and is instantiable; method bodies raise
``NotImplementedError`` loudly (see ``core.providers._not_wired``). No cloud SDK
(``azure.*``) is imported until a body is actually filled in.
"""
