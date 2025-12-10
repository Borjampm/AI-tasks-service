from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Question(_message.Message):
    __slots__ = ("question",)
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    question: str
    def __init__(self, question: _Optional[str] = ...) -> None: ...

class Answer(_message.Message):
    __slots__ = ("answer", "sequence")
    ANSWER_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    answer: str
    sequence: int
    def __init__(self, answer: _Optional[str] = ..., sequence: _Optional[int] = ...) -> None: ...
