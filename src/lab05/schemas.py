"""Strict game content contracts shared by generators and the demo."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Content(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Quest(Content):
    title: Text = Field(min_length=3, max_length=80)
    giver: Text = Field(max_length=80)
    objective: Text = Field(max_length=300)
    steps: list[Text] = Field(min_length=2, max_length=6)
    reward: Text = Field(max_length=150)
    difficulty: int = Field(ge=1, le=5)

    @field_validator('steps')
    @classmethod
    def distinct_steps(cls, steps):
        if len({s.casefold() for s in steps}) != len(steps):
            raise ValueError('Quest steps must be distinct')
        return steps


class Item(Content):
    name: Text = Field(min_length=3, max_length=80)
    type: Literal['weapon', 'armor', 'consumable', 'quest']
    rarity: Literal['common', 'rare', 'epic', 'legendary']
    description: Text = Field(max_length=300)
    stats: dict[Text, Annotated[int, Field(ge=0, le=100)]] = Field(default_factory=dict, max_length=6)


class DialogueTurn(Content):
    npc: Text = Field(max_length=80)
    text: Text = Field(max_length=500)
    emotion: Literal['neutral', 'happy', 'angry', 'afraid', 'sad'] = 'neutral'
    options: list[Text] = Field(min_length=2, max_length=4)

    @field_validator('text')
    @classmethod
    def sixty_words(cls, text):
        if len(text.split()) > 60:
            raise ValueError('Reply exceeds 60 words')
        return text
