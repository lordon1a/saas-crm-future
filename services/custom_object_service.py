import logging
from typing import Dict, Any, List, Optional
from flask import current_app
from models import db
from models_crm import CustomObject, CustomObjectRecord, EntityLink

logger = logging.getLogger(__name__)

class CustomObjectService:
    
    # --- Custom Object Schema Management ---
    
    @staticmethod
    def create_custom_object(workspace_id: int, name: str, singular_label: str = None,
                             plural_label: str = None, plural_name: str = None,
                             description: str = None, icon: str = 'fas fa-cube',
                             icon_color: str = '#6366f1', schema_config: list = None) -> CustomObject:
        try:
            custom_obj = CustomObject(
                workspace_id=workspace_id,
                name=name,
                singular_label=singular_label or name,
                plural_label=plural_label or plural_name or name,
                plural_name=plural_name,
                description=description,
                icon=icon,
                icon_color=icon_color,
                schema_config=schema_config or []
            )
            db.session.add(custom_obj)
            db.session.commit()
            logger.info(f"Custom object '{name}' created for workspace {workspace_id}")
            return custom_obj
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating custom object: {str(e)}")
            raise e

    @staticmethod
    def get_custom_objects(workspace_id: int) -> List[CustomObject]:
        return CustomObject.query.filter_by(workspace_id=workspace_id, is_active=True).all()

    @staticmethod
    def get_custom_object(workspace_id: int, obj_id: int) -> Optional[CustomObject]:
        return CustomObject.query.filter_by(workspace_id=workspace_id, id=obj_id, is_active=True).first()

    @staticmethod
    def update_custom_object_schema(workspace_id: int, obj_id: int, data: Dict[str, Any]) -> CustomObject:
        try:
            obj = CustomObjectService.get_custom_object(workspace_id, obj_id)
            if not obj:
                raise ValueError("Custom object not found")
                
            if 'singular_label' in data: obj.singular_label = data['singular_label']
            if 'plural_label' in data: obj.plural_label = data['plural_label']
            if 'plural_name' in data: obj.plural_name = data['plural_name']
            if 'description' in data: obj.description = data['description']
            if 'icon' in data: obj.icon = data['icon']
            if 'icon_color' in data: obj.icon_color = data['icon_color']
            if 'schema_config' in data: obj.schema_config = data['schema_config']
            
            db.session.commit()
            return obj
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating custom object: {str(e)}")
            raise e

    @staticmethod
    def delete_custom_object(workspace_id: int, obj_id: int) -> bool:
        try:
            obj = CustomObjectService.get_custom_object(workspace_id, obj_id)
            if obj:
                obj.is_active = False # soft delete
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting custom object: {str(e)}")
            raise e
            
    # --- Custom Object Record Management ---
    
    @staticmethod
    def create_record(workspace_id: int, custom_object_id: int, record_name: str, properties: Dict[str, Any], user_id: int = None) -> CustomObjectRecord:
        try:
            obj = CustomObjectService.get_custom_object(workspace_id, custom_object_id)
            if not obj:
                raise ValueError("Custom object not found or inactive")
                
            record = CustomObjectRecord(
                workspace_id=workspace_id,
                custom_object_id=custom_object_id,
                record_name=record_name,
                properties=properties,
                created_by=user_id
            )
            db.session.add(record)
            db.session.commit()
            return record
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating custom object record: {str(e)}")
            raise e

    @staticmethod
    def get_records(workspace_id: int, custom_object_id: int) -> List[CustomObjectRecord]:
        return CustomObjectRecord.query.filter_by(workspace_id=workspace_id, custom_object_id=custom_object_id).all()

    @staticmethod
    def get_record(workspace_id: int, record_id: int) -> Optional[CustomObjectRecord]:
        return CustomObjectRecord.query.filter_by(workspace_id=workspace_id, id=record_id).first()

    @staticmethod
    def update_record(workspace_id: int, record_id: int, data: Dict[str, Any]) -> CustomObjectRecord:
        try:
            record = CustomObjectService.get_record(workspace_id, record_id)
            if not record:
                raise ValueError("Record not found")
                
            if 'record_name' in data:
                record.record_name = data['record_name']
            if 'properties' in data:
                # Merge current properties with new ones
                from sqlalchemy.orm.attributes import flag_modified
                current_props = dict(record.properties) if record.properties else {}
                current_props.update(data['properties'])
                record.properties = current_props
                flag_modified(record, "properties")
                
            db.session.commit()
            return record
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating custom object record: {str(e)}")
            raise e
            
    # --- Polymorphic Linking ---
    
    @staticmethod
    def create_link(workspace_id: int, from_type: str, from_id: int, to_type: str, to_id: int, label: str = None) -> EntityLink:
        try:
            link = EntityLink(
                workspace_id=workspace_id,
                from_entity_type=from_type,
                from_entity_id=from_id,
                to_entity_type=to_type,
                to_entity_id=to_id,
                relationship_label=label
            )
            db.session.add(link)
            db.session.commit()
            return link
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error linking entities: {str(e)}")
            raise e

    @staticmethod
    def get_links_for_entity(workspace_id: int, entity_type: str, entity_id: int) -> List[EntityLink]:
        # Get both forward and reverse links
        from_links = EntityLink.query.filter_by(workspace_id=workspace_id, from_entity_type=entity_type, from_entity_id=entity_id).all()
        to_links = EntityLink.query.filter_by(workspace_id=workspace_id, to_entity_type=entity_type, to_entity_id=entity_id).all()
        return from_links + to_links

    @staticmethod
    def delete_link(workspace_id: int, link_id: int) -> bool:
        try:
            link = EntityLink.query.filter_by(workspace_id=workspace_id, id=link_id).first()
            if link:
                db.session.delete(link)
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting link: {str(e)}")
            raise e
