from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Analysis endpoints removed - now handled by spending_analysis_tool
# This keeps the router structure but removes duplicate functionality
