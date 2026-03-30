"""
User profile management for the Auto-Apply module.
Handles profile CRUD and resume storage/parsing.
"""

import os
from datetime import datetime
from typing import Optional

from . import db, storage
from .models import UserProfile, ProfileCreateRequest, ProfileUpdateRequest


class UserProfileManager:
    """Manages user profiles in DynamoDB with resume files in S3."""

    def create_profile(self, user_id: str, request: ProfileCreateRequest) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(
            user_id=user_id,
            email=request.email,
            name=request.name,
            phone=request.phone,
            linkedin_url=request.linkedin_url,
            summary=request.summary,
            skills=request.skills,
            target_roles=request.target_roles,
            target_companies=request.target_companies,
            blacklist_companies=request.blacklist_companies,
            min_salary=request.min_salary,
            preferred_locations=request.preferred_locations,
            preferred_workplace=request.preferred_workplace,
            preferred_experience_levels=request.preferred_experience_levels,
            common_answers=request.common_answers,
        )
        db.put_item(db.PROFILES_TABLE, profile.model_dump())
        return profile

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get a user profile by user_id."""
        item = db.get_item(db.PROFILES_TABLE, {"user_id": user_id})
        if item:
            return UserProfile(**item)
        return None

    def update_profile(self, user_id: str, request: ProfileUpdateRequest) -> Optional[UserProfile]:
        """Update an existing profile with non-None fields from the request."""
        profile = self.get_profile(user_id)
        if not profile:
            return None

        update_data = request.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

        profile.updated_at = datetime.now().isoformat()
        db.put_item(db.PROFILES_TABLE, profile.model_dump())
        return profile

    def delete_profile(self, user_id: str) -> bool:
        """Delete a user profile."""
        return db.delete_item(db.PROFILES_TABLE, {"user_id": user_id})

    async def upload_resume(self, user_id: str, filename: str, file_bytes: bytes) -> dict:
        """Upload and parse a resume PDF/DOCX. Links to the ATS parser for extraction."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"

        # Save the original file
        s3_key = storage.user_resume_path(user_id, ext)
        storage.save_blob(s3_key, file_bytes, f"application/{ext}")

        # Parse the resume using the ATS resume parser
        resume_text = ""
        resume_id = None
        try:
            from ats.resume_parser import parse_resume
            from ats import storage as ats_storage

            parsed = await parse_resume(filename, file_bytes)

            # Also extract skills using the ATS skill extractor
            from ats.skill_extractor import extract_skills_from_text
            taxonomy_skills = extract_skills_from_text(parsed.raw_text)
            existing = {s.lower() for s in parsed.skills}
            for skill in taxonomy_skills:
                if skill.lower() not in existing:
                    parsed.skills.append(skill)
                    existing.add(skill.lower())

            # Save the parsed resume in ATS storage too
            await ats_storage.save_resume_file(parsed.resume_id, filename, file_bytes)
            await ats_storage.save_parsed_resume(parsed)

            resume_text = parsed.raw_text
            resume_id = parsed.resume_id

            # Save resume text for LLM context
            storage.save_text(storage.user_resume_text_path(user_id), resume_text)

            # Update profile with resume info and parsed skills
            profile = self.get_profile(user_id)
            if profile:
                profile.resume_s3_key = s3_key
                profile.resume_text = resume_text[:5000]  # Truncate for DB storage
                profile.resume_id = resume_id

                # Merge parsed skills into profile skills
                profile_skills_lower = {s.lower() for s in profile.skills}
                for skill in parsed.skills:
                    if skill.lower() not in profile_skills_lower:
                        profile.skills.append(skill)
                        profile_skills_lower.add(skill.lower())

                # Update contact info if not already set
                if not profile.name and parsed.contact_info.name:
                    profile.name = parsed.contact_info.name
                if not profile.phone and parsed.contact_info.phone:
                    profile.phone = parsed.contact_info.phone
                if not profile.linkedin_url and parsed.contact_info.linkedin_url:
                    profile.linkedin_url = parsed.contact_info.linkedin_url

                profile.updated_at = datetime.now().isoformat()
                db.put_item(db.PROFILES_TABLE, profile.model_dump())

            return {
                "resume_id": resume_id,
                "filename": filename,
                "s3_key": s3_key,
                "text_length": len(resume_text),
                "skills_found": len(parsed.skills),
                "experience_count": len(parsed.work_experience),
                "education_count": len(parsed.education),
                "message": "Resume uploaded and parsed successfully",
            }

        except Exception as e:
            # Even if parsing fails, the file is saved
            return {
                "resume_id": None,
                "filename": filename,
                "s3_key": s3_key,
                "text_length": len(resume_text),
                "skills_found": 0,
                "experience_count": 0,
                "education_count": 0,
                "message": f"Resume uploaded but parsing failed: {str(e)}",
            }
