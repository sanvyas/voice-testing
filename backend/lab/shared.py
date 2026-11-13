"""Endpoints the product's app also needs (settings summary, speech to text, voice samples): open to the admin token or any business link."""
from fastapi import APIRouter, Depends

from assistant.access import any_member

shared = APIRouter(dependencies=[Depends(any_member)])
