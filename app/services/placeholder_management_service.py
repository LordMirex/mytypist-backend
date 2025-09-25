"""
Advanced Placeholder Management System
Handles individual placeholder styling, address comma-breaking, signature positioning, and image pixel placement
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean, Float
from database import Base
from app.models.template import Template

logger = logging.getLogger(__name__)


class PlaceholderStyling(Base):
    """Individual placeholder styling configuration"""
    __tablename__ = "placeholder_styling"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=False, index=True)
    placeholder_name = Column(String(100), nullable=False, index=True)
    placeholder_type = Column(String(50), nullable=False)  # text, address, signature, image, date

    # Position and sizing
    position_x = Column(Float, default=0)
    position_y = Column(Float, default=0)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)

    # Styling options
    styling_config = Column(JSON, nullable=True)

    # Special behaviors
    break_on_comma = Column(Boolean, default=False)  # For addresses
    preserve_aspect_ratio = Column(Boolean, default=True)  # For images/signatures
    auto_resize = Column(Boolean, default=True)

    # Admin settings
    is_active = Column(Boolean, default=True)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)


class PlaceholderManagementService:
    """
    Advanced placeholder management with individual styling support
    Handles the logic where user types one address but it applies to multiple
    placeholders with their individual styling
    """

    @staticmethod
    def set_placeholder_styling(
        db: Session,
        template_id: int,
        placeholder_name: str,
        styling_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Set individual styling for a specific placeholder
        Admin can configure each placeholder individually even if they have the same name
        """
        try:
            # Check if styling already exists
            existing_styling = db.query(PlaceholderStyling).filter(
                PlaceholderStyling.template_id == template_id,
                PlaceholderStyling.placeholder_name == placeholder_name
            ).first()

            if existing_styling:
                # Update existing styling
                existing_styling.position_x = styling_config.get('position_x', existing_styling.position_x)
                existing_styling.position_y = styling_config.get('position_y', existing_styling.position_y)
                existing_styling.width = styling_config.get('width', existing_styling.width)
                existing_styling.height = styling_config.get('height', existing_styling.height)
                existing_styling.break_on_comma = styling_config.get('break_on_comma', existing_styling.break_on_comma)
                existing_styling.preserve_aspect_ratio = styling_config.get('preserve_aspect_ratio', existing_styling.preserve_aspect_ratio)
                existing_styling.auto_resize = styling_config.get('auto_resize', existing_styling.auto_resize)
                existing_styling.styling_config = styling_config.get('styling_config', existing_styling.styling_config)

                db.commit()
                styling = existing_styling
            else:
                # Create new styling
                styling = PlaceholderStyling(
                    template_id=template_id,
                    placeholder_name=placeholder_name,
                    placeholder_type=styling_config.get('type', 'text'),
                    position_x=styling_config.get('position_x', 0),
                    position_y=styling_config.get('position_y', 0),
                    width=styling_config.get('width'),
                    height=styling_config.get('height'),
                    break_on_comma=styling_config.get('break_on_comma', False),
                    preserve_aspect_ratio=styling_config.get('preserve_aspect_ratio', True),
                    auto_resize=styling_config.get('auto_resize', True),
                    styling_config=styling_config.get('styling_config', {})
                )

                db.add(styling)
                db.commit()
                db.refresh(styling)

            logger.info(f"Placeholder styling set for {placeholder_name} in template {template_id}")

            return {
                "success": True,
                "placeholder_id": styling.id,
                "template_id": template_id,
                "placeholder_name": placeholder_name,
                "styling": {
                    "position_x": styling.position_x,
                    "position_y": styling.position_y,
                    "width": styling.width,
                    "height": styling.height,
                    "break_on_comma": styling.break_on_comma,
                    "preserve_aspect_ratio": styling.preserve_aspect_ratio,
                    "auto_resize": styling.auto_resize,
                    "styling_config": styling.styling_config
                }
            }

        except Exception as e:
            logger.error(f"Failed to set placeholder styling: {e}")
            raise

    @staticmethod
    def get_placeholder_styling(
        db: Session,
        template_id: int,
        placeholder_name: str = None
    ) -> Dict[str, Any]:
        """Get styling configuration for placeholder(s)"""
        try:
            query = db.query(PlaceholderStyling).filter(
                PlaceholderStyling.template_id == template_id,
                PlaceholderStyling.is_active == True
            )

            if placeholder_name:
                query = query.filter(PlaceholderStyling.placeholder_name == placeholder_name)

            stylings = query.all()

            result = {}
            for styling in stylings:
                result[styling.placeholder_name] = {
                    "id": styling.id,
                    "type": styling.placeholder_type,
                    "position_x": styling.position_x,
                    "position_y": styling.position_y,
                    "width": styling.width,
                    "height": styling.height,
                    "break_on_comma": styling.break_on_comma,
                    "preserve_aspect_ratio": styling.preserve_aspect_ratio,
                    "auto_resize": styling.auto_resize,
                    "styling_config": styling.styling_config or {}
                }

            return {
                "success": True,
                "template_id": template_id,
                "placeholder_stylings": result
            }

        except Exception as e:
            logger.error(f"Failed to get placeholder styling: {e}")
            raise

    @staticmethod
    def process_user_input_with_individual_styling(
        db: Session,
        template_id: int,
        user_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process user input and apply individual styling to each placeholder
        This is the core logic you requested:
        - User types one address, but system applies it to multiple address placeholders
        - Each placeholder maintains its individual styling (position, formatting, etc.)
        """
        try:
            # Get all placeholder stylings for this template
            stylings_result = PlaceholderManagementService.get_placeholder_styling(
                db, template_id
            )

            if not stylings_result["success"]:
                raise Exception("Failed to get placeholder stylings")

            placeholder_stylings = stylings_result["placeholder_stylings"]
            processed_placeholders = {}

            # Process each user input
            for input_name, input_value in user_inputs.items():
                # Find all placeholders that match this input name
                matching_placeholders = [
                    (name, config) for name, config in placeholder_stylings.items()
                    if name.lower() == input_name.lower() or
                    name.lower().replace('_', '').replace('-', '') == input_name.lower().replace('_', '').replace('-', '')
                ]

                # Apply individual styling to each matching placeholder
                for placeholder_name, styling_config in matching_placeholders:
                    processed_value = PlaceholderManagementService._apply_individual_styling(
                        input_value, styling_config, placeholder_name
                    )

                    processed_placeholders[placeholder_name] = {
                        "value": processed_value,
                        "styling": styling_config,
                        "position": {
                            "x": styling_config["position_x"],
                            "y": styling_config["position_y"]
                        },
                        "dimensions": {
                            "width": styling_config["width"],
                            "height": styling_config["height"]
                        }
                    }

            logger.info(f"Processed {len(processed_placeholders)} placeholders with individual styling")

            return {
                "success": True,
                "template_id": template_id,
                "processed_placeholders": processed_placeholders,
                "total_placeholders": len(processed_placeholders)
            }

        except Exception as e:
            logger.error(f"Failed to process user input with styling: {e}")
            raise

    @staticmethod
    def _apply_individual_styling(
        value: Any,
        styling_config: Dict[str, Any],
        placeholder_name: str
    ) -> Any:
        """
        Apply individual styling to a placeholder value
        Handles special cases like address comma-breaking, signature positioning, etc.
        """
        try:
            placeholder_type = styling_config.get("type", "text")
            processed_value = value

            # Address handling with comma breaks
            if placeholder_type == "address" and styling_config.get("break_on_comma", False):
                if isinstance(value, str) and "," in value:
                    # Split on commas and create line breaks
                    address_parts = [part.strip() for part in value.split(",")]
                    processed_value = "\n".join(address_parts)
                    logger.debug(f"Applied comma-break formatting to address placeholder: {placeholder_name}")

            # Signature handling
            elif placeholder_type == "signature":
                # For signatures, we maintain the base64 data but add positioning metadata
                if isinstance(value, str) and value.startswith("data:image"):
                    processed_value = {
                        "signature_data": value,
                        "position_x": styling_config["position_x"],
                        "position_y": styling_config["position_y"],
                        "max_width": styling_config.get("width", 200),
                        "max_height": styling_config.get("height", 100),
                        "preserve_aspect_ratio": styling_config.get("preserve_aspect_ratio", True)
                    }
                    logger.debug(f"Applied signature positioning to: {placeholder_name}")

            # Image handling with pixel positioning
            elif placeholder_type == "image":
                if isinstance(value, str):
                    processed_value = {
                        "image_data": value,
                        "position_x": styling_config["position_x"],
                        "position_y": styling_config["position_y"],
                        "width": styling_config.get("width"),
                        "height": styling_config.get("height"),
                        "preserve_aspect_ratio": styling_config.get("preserve_aspect_ratio", True),
                        "auto_resize": styling_config.get("auto_resize", True)
                    }
                    logger.debug(f"Applied image positioning to: {placeholder_name}")

            # Date formatting
            elif placeholder_type == "date":
                date_format = styling_config.get("styling_config", {}).get("date_format", "%B %d, %Y")
                if isinstance(value, str):
                    try:
                        from datetime import datetime
                        parsed_date = datetime.strptime(value, "%Y-%m-%d")
                        processed_value = parsed_date.strftime(date_format)
                        logger.debug(f"Applied date formatting to: {placeholder_name}")
                    except:
                        # If parsing fails, keep original value
                        processed_value = value

            # Text formatting (font size, color, etc.)
            elif placeholder_type == "text":
                text_styling = styling_config.get("styling_config", {})
                if text_styling:
                    processed_value = {
                        "text": value,
                        "font_size": text_styling.get("font_size", 12),
                        "font_color": text_styling.get("font_color", "#000000"),
                        "font_weight": text_styling.get("font_weight", "normal"),
                        "font_style": text_styling.get("font_style", "normal"),
                        "text_align": text_styling.get("text_align", "left")
                    }
                    logger.debug(f"Applied text styling to: {placeholder_name}")

            return processed_value

        except Exception as e:
            logger.error(f"Failed to apply individual styling to {placeholder_name}: {e}")
            return value  # Return original value if styling fails

    @staticmethod
    def get_template_placeholder_map(
        db: Session,
        template_id: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a map of input names to all their corresponding placeholders
        This helps the frontend understand which placeholders will be affected by each input
        """
        try:
            stylings_result = PlaceholderManagementService.get_placeholder_styling(
                db, template_id
            )

            if not stylings_result["success"]:
                return {"success": False, "error": "Failed to get placeholder stylings"}

            placeholder_stylings = stylings_result["placeholder_stylings"]
            input_map = {}

            # Group placeholders by their base name (ignoring case and special characters)
            for placeholder_name, styling_config in placeholder_stylings.items():
                # Normalize the placeholder name for grouping
                base_name = placeholder_name.lower().replace('_', '').replace('-', '').replace(' ', '')

                if base_name not in input_map:
                    input_map[base_name] = []

                input_map[base_name].append({
                    "placeholder_name": placeholder_name,
                    "type": styling_config["type"],
                    "position": {
                        "x": styling_config["position_x"],
                        "y": styling_config["position_y"]
                    },
                    "styling": styling_config
                })

            return {
                "success": True,
                "template_id": template_id,
                "input_map": input_map,
                "total_inputs": len(input_map),
                "total_placeholders": len(placeholder_stylings)
            }

        except Exception as e:
            logger.error(f"Failed to get template placeholder map: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def validate_placeholder_styling(
        styling_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate placeholder styling configuration"""
        errors = []
        warnings = []

        # Validate position values
        if "position_x" in styling_config:
            if not isinstance(styling_config["position_x"], (int, float)):
                errors.append("position_x must be a number")
            elif styling_config["position_x"] < 0:
                warnings.append("position_x is negative, may cause rendering issues")

        if "position_y" in styling_config:
            if not isinstance(styling_config["position_y"], (int, float)):
                errors.append("position_y must be a number")
            elif styling_config["position_y"] < 0:
                warnings.append("position_y is negative, may cause rendering issues")

        # Validate dimensions
        if "width" in styling_config and styling_config["width"] is not None:
            if not isinstance(styling_config["width"], (int, float)) or styling_config["width"] <= 0:
                errors.append("width must be a positive number")

        if "height" in styling_config and styling_config["height"] is not None:
            if not isinstance(styling_config["height"], (int, float)) or styling_config["height"] <= 0:
                errors.append("height must be a positive number")

        # Validate type
        valid_types = ["text", "address", "signature", "image", "date", "number", "email", "phone"]
        if "type" in styling_config and styling_config["type"] not in valid_types:
            errors.append(f"type must be one of: {', '.join(valid_types)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
