"""
Advanced Batch Processing Service
Smart input consolidation for multiple document generation with individual styling preservation
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from sqlalchemy.orm import Session
from collections import defaultdict, Counter
import hashlib
import json

from app.models.template import Template
from app.models.document import Document

logger = logging.getLogger(__name__)


class BatchInputConsolidator:
    """Smart input consolidation for batch document processing"""

    @staticmethod
    async def consolidate_batch_inputs(
        db: Session,
        templates: List[Template],
        batch_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Consolidate duplicate inputs across multiple documents while preserving individual styling

        Example:
        - 5 documents with 'name' placeholder -> User types once, applied to all 5 with their individual styling
        - Different font sizes, positions maintained per document
        """

        try:
            # Extract all placeholders from templates
            template_placeholders = {}
            for template in templates:
                placeholders = await BatchInputConsolidator._extract_template_placeholders(template)
                template_placeholders[template.id] = placeholders

            # Analyze input patterns across all documents
            placeholder_analysis = BatchInputConsolidator._analyze_placeholder_patterns(
                batch_documents, template_placeholders
            )

            # Create consolidated input form
            consolidated_form = BatchInputConsolidator._create_consolidated_form(
                placeholder_analysis
            )

            # Generate mapping for individual document styling
            styling_mappings = BatchInputConsolidator._create_styling_mappings(
                batch_documents, template_placeholders, placeholder_analysis
            )

            return {
                "success": True,
                "consolidated_placeholders": consolidated_form,
                "styling_mappings": styling_mappings,
                "summary": {
                    "original_input_count": sum(len(doc.get("placeholder_data", {})) for doc in batch_documents),
                    "consolidated_input_count": len(consolidated_form),
                    "reduction_percentage": BatchInputConsolidator._calculate_reduction_percentage(
                        sum(len(doc.get("placeholder_data", {})) for doc in batch_documents),
                        len(consolidated_form)
                    ),
                    "duplicate_groups": len([group for group in placeholder_analysis.values() if len(group["documents"]) > 1])
                }
            }

        except Exception as e:
            logger.error(f"Batch input consolidation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "consolidated_placeholders": [],
                "styling_mappings": {},
                "summary": {}
            }

    @staticmethod
    async def _extract_template_placeholders(template: Template) -> Dict[str, Any]:
        """Extract placeholder information from template"""

        # This would analyze the template file to extract placeholders
        # For now, we'll simulate the extraction
        placeholders = {}

        if hasattr(template, 'placeholder_config') and template.placeholder_config:
            placeholders = json.loads(template.placeholder_config)
        else:
            # Fallback: extract from template content or metadata
            placeholders = {
                "name": {"type": "text", "required": True, "styling": {}},
                "date": {"type": "date", "required": False, "styling": {}},
                "address": {"type": "address", "required": False, "styling": {"break_on_comma": True}},
                "signature": {"type": "signature", "required": False, "styling": {"position": {"x": 0, "y": 0}}}
            }

        return placeholders

    @staticmethod
    def _analyze_placeholder_patterns(
        batch_documents: List[Dict[str, Any]],
        template_placeholders: Dict[int, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze patterns in placeholder usage across documents"""

        placeholder_groups = defaultdict(lambda: {
            "documents": [],
            "values": [],
            "styling_variations": [],
            "placeholder_type": None,
            "consolidation_key": None
        })

        for doc_idx, doc in enumerate(batch_documents):
            template_id = doc.get("template_id")
            placeholder_data = doc.get("placeholder_data", {})

            template_config = template_placeholders.get(template_id, {})

            for placeholder_name, value in placeholder_data.items():
                # Create consolidation key based on placeholder semantic meaning
                consolidation_key = BatchInputConsolidator._create_consolidation_key(
                    placeholder_name, template_config.get(placeholder_name, {})
                )

                placeholder_groups[consolidation_key]["documents"].append({
                    "doc_index": doc_idx,
                    "template_id": template_id,
                    "placeholder_name": placeholder_name,
                    "value": value
                })

                placeholder_groups[consolidation_key]["values"].append(value)

                # Extract styling information
                styling = template_config.get(placeholder_name, {}).get("styling", {})
                placeholder_groups[consolidation_key]["styling_variations"].append({
                    "doc_index": doc_idx,
                    "styling": styling
                })

                placeholder_groups[consolidation_key]["placeholder_type"] = template_config.get(
                    placeholder_name, {}
                ).get("type", "text")

                placeholder_groups[consolidation_key]["consolidation_key"] = consolidation_key

        return dict(placeholder_groups)

    @staticmethod
    def _create_consolidation_key(placeholder_name: str, placeholder_config: Dict[str, Any]) -> str:
        """Create a key for grouping similar placeholders"""

        # Normalize placeholder names for consolidation
        # e.g., "client_name", "customer_name", "name" -> "name"

        normalized_name = placeholder_name.lower()

        # Common name variations
        name_variations = ["name", "client_name", "customer_name", "user_name", "full_name"]
        if any(var in normalized_name for var in name_variations):
            return "name"

        # Address variations
        address_variations = ["address", "location", "street", "addr"]
        if any(var in normalized_name for var in address_variations):
            return "address"

        # Date variations
        date_variations = ["date", "time", "created", "issued"]
        if any(var in normalized_name for var in date_variations):
            return "date"

        # Signature variations
        signature_variations = ["signature", "sign", "signed_by"]
        if any(var in normalized_name for var in signature_variations):
            return "signature"

        # Email variations
        email_variations = ["email", "mail", "e_mail"]
        if any(var in normalized_name for var in email_variations):
            return "email"

        # Phone variations
        phone_variations = ["phone", "mobile", "cell", "tel", "telephone"]
        if any(var in normalized_name for var in phone_variations):
            return "phone"

        # If no match found, use original name
        return normalized_name

    @staticmethod
    def _create_consolidated_form(placeholder_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create consolidated input form for user"""

        consolidated_form = []

        for consolidation_key, group_data in placeholder_analysis.items():
            # Only consolidate if multiple documents use this placeholder
            if len(group_data["documents"]) > 1:
                # Get most common value as default
                value_counts = Counter(group_data["values"])
                most_common_value = value_counts.most_common(1)[0][0] if value_counts else ""

                consolidated_form.append({
                    "consolidation_key": consolidation_key,
                    "display_name": BatchInputConsolidator._get_display_name(consolidation_key),
                    "placeholder_type": group_data["placeholder_type"],
                    "default_value": most_common_value,
                    "required": True,
                    "applies_to_documents": len(group_data["documents"]),
                    "document_list": [doc["doc_index"] for doc in group_data["documents"]],
                    "styling_note": f"Will be applied with individual styling to {len(group_data['documents'])} documents"
                })
            else:
                # Single document placeholder - keep as individual input
                doc_data = group_data["documents"][0]
                consolidated_form.append({
                    "consolidation_key": consolidation_key,
                    "display_name": f"{BatchInputConsolidator._get_display_name(consolidation_key)} (Document {doc_data['doc_index'] + 1})",
                    "placeholder_type": group_data["placeholder_type"],
                    "default_value": doc_data["value"],
                    "required": False,
                    "applies_to_documents": 1,
                    "document_list": [doc_data["doc_index"]],
                    "styling_note": "Individual styling for single document"
                })

        # Sort by number of documents (most common first)
        consolidated_form.sort(key=lambda x: x["applies_to_documents"], reverse=True)

        return consolidated_form

    @staticmethod
    def _create_styling_mappings(
        batch_documents: List[Dict[str, Any]],
        template_placeholders: Dict[int, Dict[str, Any]],
        placeholder_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create mappings to preserve individual document styling"""

        styling_mappings = {}

        for doc_idx, doc in enumerate(batch_documents):
            template_id = doc.get("template_id")
            template_config = template_placeholders.get(template_id, {})

            doc_styling = {}

            for placeholder_name, value in doc.get("placeholder_data", {}).items():
                consolidation_key = BatchInputConsolidator._create_consolidation_key(
                    placeholder_name, template_config.get(placeholder_name, {})
                )

                # Store styling information for this specific document
                doc_styling[consolidation_key] = {
                    "original_placeholder_name": placeholder_name,
                    "styling": template_config.get(placeholder_name, {}).get("styling", {}),
                    "position": template_config.get(placeholder_name, {}).get("position", {}),
                    "formatting": template_config.get(placeholder_name, {}).get("formatting", {})
                }

            styling_mappings[f"document_{doc_idx}"] = {
                "template_id": template_id,
                "styling_config": doc_styling
            }

        return styling_mappings

    @staticmethod
    def _get_display_name(consolidation_key: str) -> str:
        """Get user-friendly display name for consolidated input"""

        display_names = {
            "name": "Full Name",
            "address": "Address",
            "date": "Date",
            "signature": "Signature",
            "email": "Email Address",
            "phone": "Phone Number",
            "company": "Company Name",
            "position": "Job Title/Position"
        }

        return display_names.get(consolidation_key, consolidation_key.replace("_", " ").title())

    @staticmethod
    def _calculate_reduction_percentage(original_count: int, consolidated_count: int) -> float:
        """Calculate percentage reduction in input fields"""

        if original_count == 0:
            return 0.0

        reduction = ((original_count - consolidated_count) / original_count) * 100
        return round(reduction, 1)

    @staticmethod
    async def apply_consolidated_inputs_to_documents(
        consolidated_inputs: Dict[str, Any],
        styling_mappings: Dict[str, Any],
        user_input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply user's consolidated inputs to individual documents with preserved styling"""

        try:
            document_data = {}

            for doc_key, styling_config in styling_mappings.items():
                doc_placeholders = {}

                for consolidation_key, styling_info in styling_config["styling_config"].items():
                    if consolidation_key in user_input_data:
                        # Apply user input with individual document styling
                        user_value = user_input_data[consolidation_key]

                        # Apply special formatting based on placeholder type
                        formatted_value = BatchInputConsolidator._apply_placeholder_formatting(
                            user_value, styling_info, consolidation_key
                        )

                        doc_placeholders[styling_info["original_placeholder_name"]] = formatted_value

                document_data[doc_key] = {
                    "template_id": styling_config["template_id"],
                    "placeholder_data": doc_placeholders
                }

            return {
                "success": True,
                "document_data": document_data
            }

        except Exception as e:
            logger.error(f"Failed to apply consolidated inputs: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_data": {}
            }

    @staticmethod
    def _apply_placeholder_formatting(
        value: str,
        styling_info: Dict[str, Any],
        consolidation_key: str
    ) -> str:
        """Apply special formatting based on placeholder type and styling"""

        styling = styling_info.get("styling", {})

        # Address formatting with comma breaks
        if consolidation_key == "address" and styling.get("break_on_comma", False):
            # Split on commas and create line breaks
            address_parts = [part.strip() for part in value.split(",")]
            return "\n".join(address_parts)

        # Date formatting
        if consolidation_key == "date" and styling.get("format"):
            # Apply date formatting if specified
            try:
                from datetime import datetime
                if isinstance(value, str):
                    # Try to parse and reformat date
                    parsed_date = datetime.strptime(value, "%Y-%m-%d")
                    return parsed_date.strftime(styling["format"])
            except:
                pass  # Return original value if parsing fails

        # Default: return value as-is
        return value


class BatchDocumentGenerator:
    """Generate multiple documents efficiently with consolidated inputs"""

    @staticmethod
    async def generate_batch_with_consolidation(
        db: Session,
        batch_id: str,
        document_ids: List[int],
        consolidated_inputs: Dict[str, Any],
        user_input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate batch documents using consolidated inputs"""

        try:
            # Apply consolidated inputs to individual documents
            application_result = await BatchInputConsolidator.apply_consolidated_inputs_to_documents(
                consolidated_inputs,
                consolidated_inputs["styling_mappings"],
                user_input_data
            )

            if not application_result["success"]:
                return application_result

            # Generate documents with applied data
            generation_results = []

            for doc_id in document_ids:
                document = db.query(Document).filter(Document.id == doc_id).first()
                if not document:
                    continue

                doc_key = f"document_{document_ids.index(doc_id)}"
                doc_data = application_result["document_data"].get(doc_key, {})

                # Generate individual document
                result = await BatchDocumentGenerator._generate_single_document(
                    db, document, doc_data["placeholder_data"]
                )

                generation_results.append({
                    "document_id": doc_id,
                    "success": result["success"],
                    "file_path": result.get("file_path"),
                    "error": result.get("error")
                })

            return {
                "success": True,
                "batch_id": batch_id,
                "results": generation_results,
                "successful_count": sum(1 for r in generation_results if r["success"]),
                "total_count": len(generation_results)
            }

        except Exception as e:
            logger.error(f"Batch generation with consolidation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    @staticmethod
    async def _generate_single_document(
        db: Session,
        document: Document,
        placeholder_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a single document with placeholder data"""

        try:
            # This would integrate with your document generation service
            from app.services.document_service import DocumentService

            result = await DocumentService.generate_document_with_placeholders(
                db, document.id, placeholder_data
            )

            return result

        except Exception as e:
            logger.error(f"Single document generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
