"""Type-safe Pydantic models for tool I/O."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict


class GetIncidentRequest(BaseModel):
    """Request model for get_incident tool."""
    incident_id: str = Field(
        ...,
        description="Incident ID, e.g. INC-4291"
    )


class GetIncidentResponse(BaseModel):
    """Response model for get_incident tool."""
    
    status: str = Field(..., description="Status (success/error/pending)")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is error")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class FetchTelemetryRequest(BaseModel):
    """Request model for fetch_telemetry tool."""
    site_id: str = Field(
        ...,
        description="Cell site ID, e.g. MAN-372"
    )


class FetchTelemetryResponse(BaseModel):
    """Response model for fetch_telemetry tool."""
    
    status: str = Field(..., description="Status (success/error/pending)")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is error")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class FetchCustomerImpactRequest(BaseModel):
    """Request model for fetch_customer_impact tool."""
    site_id: str = Field(
        ...,
        description="Cell site ID, e.g. MAN-372"
    )


class FetchCustomerImpactResponse(BaseModel):
    """Response model for fetch_customer_impact tool."""
    
    status: str = Field(..., description="Status (success/error/pending)")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is error")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class ApplyChangeRequest(BaseModel):
    """Request model for apply_change tool."""
    incident_id: str = Field(
        ...,
        description="ITSM incident ID"
    )
    site_id: str = Field(
        ...,
        description="Cell site ID"
    )
    action: str = Field(
        ...,
        description="Corrective action to apply"
    )
    rationale: str = Field(
        ...,
        description="Reason for choosing this action"
    )
    approved: bool = Field(
        ...,
        description="Must be true to apply change"
    )
    approver: str = Field(
        ...,
        description="Approver identifier"
    )


class ApplyChangeResponse(BaseModel):
    """Response model for apply_change tool."""
    
    status: str = Field(..., description="Status (success/error/pending)")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is error")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")



def parse_tool_response(response: Any) -> dict:
    """
    Parse various response types into standardized dictionary format.
    
    Args:
        response: Response from tool (dict, object, or string)
        
    Returns:
        Standardized response dictionary
    """
    if isinstance(response, dict):
        return response
    elif hasattr(response, 'dict'):
        return response.dict()
    elif hasattr(response, '__dict__'):
        return response.__dict__
    else:
        return {"data": str(response)}