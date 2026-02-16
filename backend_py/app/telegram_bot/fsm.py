"""FSM states for ad post writing flow."""
from aiogram.fsm.state import State, StatesGroup


class PostFlow(StatesGroup):
    waiting_post = State()
    waiting_button = State()
    waiting_approval = State()


class SellerFlow(StatesGroup):
    waiting_comment = State()
