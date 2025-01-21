from typing import Literal, Tuple, Dict, Optional
import time
import smtplib
import requests
import PyPDF2
from datetime import datetime, timedelta
from typing import Literal, Tuple
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging
import streamlit as st
import json
import os
import pytz
import logging

import streamlit as st
from phi.tools.zoom import ZoomTool
from phi.utils.log import logger
from streamlit_pdf_viewer import pdf_viewer



class CustomZoomTool(ZoomTool):
    def __init__(self, *, account_id: Optional[str] = None, client_id: Optional[str] = None, client_secret: Optional[str] = None, name: str = "zoom_tool"):
        super().__init__(account_id=account_id, client_id=client_id, client_secret=client_secret, name=name)
        self.token_url = "https://zoom.us/oauth/token"
        self.access_token = None
        self.token_expires_at = 0

    def get_access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at:
            return str(self.access_token)
            
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "account_credentials", "account_id": self.account_id}

        try:
            response = requests.post(self.token_url, headers=headers, data=data, auth=(self.client_id, self.client_secret))
            response.raise_for_status()

            token_info = response.json()
            self.access_token = token_info["access_token"]
            expires_in = token_info["expires_in"]
            self.token_expires_at = time.time() + expires_in - 60

            self._set_parent_token(str(self.access_token))
            return str(self.access_token)

        except requests.RequestException as e:
            logger.error(f"Error fetching access token: {e}")
            return ""

    def _set_parent_token(self, token: str) -> None:
        """Helper method to set the token in the parent ZoomTool class"""
        if token:
            self._ZoomTool__access_token = token


# Role requirements as a constant dictionary
FILE_PATH = "roles.json"

# Default roles, which will be added to the file only if it is empty
ROLE_REQUIREMENTS = {
    "ai_ml_engineer": """
        Required Skills:
        - Python, PyTorch/TensorFlow
        - Machine Learning algorithms and frameworks
        - Deep Learning and Neural Networks
        - Data preprocessing and analysis
        - MLOps and model deployment
        - RAG, LLM, Finetuning and Prompt Engineering
    """,
    "frontend_engineer": """
        Required Skills:
        - React/Vue.js/Angular
        - HTML5, CSS3, JavaScript/TypeScript
        - Responsive design
        - State management
        - Frontend testing
    """,
    "backend_engineer": """
        Required Skills:
        - Python/Java/Node.js
        - REST APIs
        - Database design and management
        - System architecture
        - Cloud services (AWS/GCP/Azure)
        - Kubernetes, Docker, CI/CD
    """
}

def load_roles():
    """Load roles from the file, or return empty dict if the file doesn't exist or is empty."""
    try:
        with open(FILE_PATH, "r") as file:
            roles = json.load(file)
            if not roles:  # If file is empty, return an empty dict
                return {}
            return roles
    except FileNotFoundError:
        return {}

def save_roles(roles):
    """Save roles to the file."""
    with open(FILE_PATH, "w") as file:
        json.dump(roles, file, indent=4)

def manage_roles():
    """Manage roles by allowing add, edit, or delete functionality."""
    
    # Load roles (either from file or default if empty)
    roles = load_roles()
    
    # If roles file is empty, add the default roles
    if not roles:
        roles = ROLE_REQUIREMENTS.copy()
        save_roles(roles)  # Save default roles immediately if the file was empty

    if "custom_roles" not in st.session_state:
        st.session_state["custom_roles"] = roles

    st.sidebar.subheader("Modify or Add Role Criteria")

    # Select or add a role
    role_choice = st.selectbox(
        "Select a role to modify or add:",
        list(st.session_state["custom_roles"].keys()) + ["Add New Role"]
    )

    if role_choice == "Add New Role":
        # Adding new role
        new_role = st.text_input("Enter the name of the new role:")
        if new_role:
            new_criteria = st.text_area("Enter the criteria for the new role:")
            if st.button("Add Role"):
                if new_role.strip() == "":
                    st.error("Role name cannot be empty.")
                elif not new_criteria.strip():
                    st.error("Please provide criteria for the new role.")
                else:
                    st.session_state["custom_roles"][new_role] = new_criteria
                    save_roles(st.session_state["custom_roles"])  # Save the new role immediately
                    st.success(f"New role '{new_role}' added successfully.")
    else:
        # Modifying or deleting an existing role
        st.markdown(f"### Current Criteria for {role_choice}:")
        st.text_area("", value=st.session_state["custom_roles"][role_choice], height=150, disabled=True)

        # Allow modifications for editable roles
        new_criteria = st.text_area(
            f"Modify the criteria for {role_choice}:",
            value=st.session_state["custom_roles"][role_choice]
        )
        
        if st.button("Save Changes"):
            if new_criteria.strip() == "":
                st.error("Criteria cannot be empty.")
            else:
                st.session_state["custom_roles"][role_choice] = new_criteria
                save_roles(st.session_state["custom_roles"])  # Save the change immediately
                st.success(f"Criteria for '{role_choice}' updated successfully.")

        # Option to delete the role
        if st.button("Delete Role"):
            del st.session_state["custom_roles"][role_choice]
            save_roles(st.session_state["custom_roles"])  # Save after deletion
            st.success(f"Role '{role_choice}' deleted successfully.")

    # Check if roles file is empty again and add default roles if needed
    if not st.session_state["custom_roles"]:
        st.session_state["custom_roles"] = ROLE_REQUIREMENTS.copy()
        save_roles(st.session_state["custom_roles"])

    return st.session_state["custom_roles"]


def schedule_meeting():
    """
    Allows the user to input a date and time for scheduling a meeting.
    Stores the data in session_state for later use.
    """
    st.sidebar.subheader("Schedule Meeting")

    # Date and Time Inputs
    meeting_date = st.date_input("Select Meeting Date:")
    meeting_time = st.time_input("Select Meeting Time:")

    # Combine date and time into a datetime object
    if meeting_date and meeting_time:
        scheduled_datetime = datetime.combine(meeting_date, meeting_time)
        st.session_state["scheduled_datetime"] = scheduled_datetime
        st.success(f"Meeting scheduled for: {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

    # Display scheduled date and time if already set
    if "scheduled_datetime" in st.session_state:
        st.sidebar.info(
            f"Scheduled Meeting:\n{st.session_state['scheduled_datetime'].strftime('%Y-%m-%d %H:%M:%S')}"
        )




def init_session_state() -> None:
    """Initialize only necessary session state variables."""
    defaults = {
        'candidate_email': "", 'openai_api_key': "", 'recruiter_email': "" ,'resume_text': "", 'analysis_complete': False,
        'is_selected': False, 'zoom_account_id': "", 'zoom_client_id': "", 'zoom_client_secret': "",
        'email_sender': "", 'email_passkey': "", 'company_name': "", 'current_pdf': None,
        'time_change_requested': False, 'scheduled_datetime': None, 'proceed_app' : False,
        'check_it' : False, 'no_button' : False, 'time_and_date' : False, 'check_again' : False, 'fragment' : False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def extract_text_from_pdf(pdf_file) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
        return ""


def analyze_resume(
    resume_text: str,
    role
) -> Tuple[bool, str]:
    try:
        # Manual response
        response = {
            "selected": True,
            "feedback": "The candidate meets over 70% of the required skills for the AI/ML Engineer role...",
            "matching_skills": ["Python", "Machine Learning", "Deep Learning", "Flask Framework", "DBMS", "C++"],
            "missing_skills": ["TensorFlow", "PyTorch", "Natural Language Processing", "Cloud Computing", "DevOps"],
            "experience_level": "junior"
        }

        # Directly return the values as a tuple
        return response["selected"], response["feedback"]

    except Exception as e:
        # Handle unexpected exceptions gracefully
        return False, f"Error analyzing resume: {str(e)}"


def send_selection_email(sender_email, sender_password, receiver_email, role, company) -> None:
    """Send an email with the given subject and body."""
    
    # Constructing the subject and body of the email
    subject = f"Congratulations! You have been selected for the {role} role"
    
    body = f"""
    Dear Candidate,
    
    Congratulations! We are pleased to inform you that you have been selected for the role of {role} at {company}.
    
    We believe you will be a great addition to the team, and we look forward to seeing the skills and expertise you will bring to this position.
    
    Please prepare yourself by reviewing relevant skills for the {role} role. You will be contacted shortly with further instructions regarding your start date and other preparations.
    
    Additionally, we will schedule a Zoom meeting soon to discuss the next steps and answer any questions you may have.
    
    Best regards,
    {company}
    """

    # Creating MIMEText object for email
    msg = MIMEText(body, 'plain', 'utf-8')
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # Sending the email through Gmail's SMTP server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()  # Start TLS encryption
        server.login(sender_email, sender_password)  # Login with the sender's credentials
        server.sendmail(sender_email, receiver_email, msg.as_string())  # Send the email


def send_rejection_email(sender_email, sender_password, receiver_email, role, company) -> None:
    """Send an email with the given subject and body."""
    
    # Constructing the subject and body of the rejection email
    subject = f"Regarding your application for the {role} role"
    
    body = f"""
    Dear Candidate,
    
    Thank you for your interest in the {role} role at {company}. Unfortunately, we regret to inform you that we will not be proceeding with your application at this time.
    
    While we were impressed with your qualifications, we have decided to move forward with other candidates who more closely match the requirements for this role.
    
    We encourage you to continue preparing and working hard to improve your skills. Please don't be discouraged—your next opportunity may be just around the corner. We welcome you to apply again for future positions with us.

    We wish you all the best in your career journey.
    
    Best regards,
    {company}
    """

    # Creating MIMEText object for email
    msg = MIMEText(body, 'plain', 'utf-8')
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # Sending the email through Gmail's SMTP server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()  # Start TLS encryption
        server.login(sender_email, sender_password)  # Login with the sender's credentials
        server.sendmail(sender_email, receiver_email, msg.as_string())  # Send the email
 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def schedule_interview(
    zoom_acc_id, zoom_client_id, zoom_secret, sender_email, 
    sender_password, receiver_email, recruiter_email, role: str, company: str, local_timezone: str
) -> None:
    try:
        # Ensure the date and time for scheduling are set
        if "scheduled_datetime" not in st.session_state:
            st.error("Please schedule a date and time for the interview first!")
            return
        
        # Step 1: Show the allocated interview time
        st.subheader("Interview Date & Time Allocation")
        
        # Check if the interview time has already been scheduled by the recruiter
        if 'scheduled_datetime' not in st.session_state:
            st.error("No interview time allocated by the recruiter yet.")
            return

        # Show the allocated interview date and time
        scheduled_datetime = st.session_state['scheduled_datetime']
        st.write(f"Your interview is scheduled for {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')} ({local_timezone})")

        # Convert the scheduled datetime to UTC for Zoom API
        local_tz = pytz.timezone(local_timezone)
        local_dt = local_tz.localize(scheduled_datetime, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        meeting_time_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # ISO 8601 format

        # Step 2: Get Zoom OAuth token
        zoom_token_url = "https://zoom.us/oauth/token"
        zoom_payload = {
            'grant_type': 'account_credentials',
            'account_id': zoom_acc_id
        }
        auth = (zoom_client_id, zoom_secret)

        token_response = requests.post(zoom_token_url, data=zoom_payload, auth=auth)
        token_response.raise_for_status()
        access_token = token_response.json().get('access_token')
        if not access_token:
            raise ValueError("Failed to fetch Zoom access token.")

        # Step 3: Schedule a Zoom meeting
        zoom_meeting_url = "https://api.zoom.us/v2/users/me/meetings"
        meeting_details = {
            "topic": f"Interview for {role}",
            "type": 2,  # Scheduled meeting
            "start_time": meeting_time_iso,
            "duration": 60,  # Meeting duration in minutes
            "timezone": "UTC",
            "settings": {
                "join_before_host": True,
                "waiting_room": False
            }
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        meeting_response = requests.post(zoom_meeting_url, json=meeting_details, headers=headers)
        meeting_response.raise_for_status()
        meeting_data = meeting_response.json()
        meeting_link = meeting_data.get('join_url')

        if not meeting_link:
            raise ValueError("Failed to schedule Zoom meeting.")

        # Step 4: Send email with meeting details
        subject = f"Interview Scheduled for {role} at {company}"
        body = f"""
        Dear Candidate,

        We are pleased to inform you that your interview for the {role} role at {company} has been scheduled.

        Meeting Details:
        - Link: {meeting_link}
        - Date: {scheduled_datetime.strftime('%Y-%m-%d')}
        - Time: {scheduled_datetime.strftime('%H:%M:%S')} ({local_timezone})

        Instructions:
        - Please ensure that you join the interview on time.
        - Test your camera and microphone in advance to ensure they are working correctly.
        - Use a quiet environment to avoid distractions during the interview.
        - Dress appropriately as you would for an in-person interview.
        - Ensure your internet connection is stable for a smooth interview experience.

        We look forward to meeting with you and discussing your qualifications for the {role} role.

        Best regards,
        {company} Hiring Team
        """

        # Properly format multiple recipients
        recipients = [receiver_email, recruiter_email]
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = ", ".join(recipients)  # Correctly format the To field
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)


    except Exception as e:
        logger.error(f"Error scheduling interview: {str(e)}")
        st.error("Unable to schedule interview. Please try again.")


def ask_for_time_change():
    """Asks the candidate if they want to change the interview time."""

    if "time_change_requested" not in st.session_state:
        st.session_state.time_change_requested = False

    current_time = st.session_state.get("scheduled_datetime", None)
    if not current_time:
        st.warning("No interview time assigned by the recruiter yet.")
        return

    st.write(f"Current interview time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Use a key for the radio button to maintain state across reruns
    change_time = st.radio("Would you like to change the interview time?", ["No", "Yes"], index=1, key="change_time_radio")
    print(change_time)
    
    if change_time == "Yes":
        st.session_state.time_change_requested = True  # set to true when user click yes
       

    elif change_time == "No":
        st.session_state.time_change_requested = False  # set to false when user click No
        st.write("You have opted to keep the original scheduled time.")

    return st.session_state.time_change_requested  # return the value to know whether to proceed with scheduling or not


import streamlit as st
import json
from datetime import datetime

def update_meeting_schedule():
    """
    Updates the meeting schedule by allowing the user to select from predefined dates and times.
    Updates st.session_state["scheduled_datetime"] accordingly.
    """
    st.sidebar.subheader("Update Meeting Schedule")

    # Load predefined available times from the JSON file
    with open(
        r"C:\Users\Admin\python_project\awesome-llm-apps\ai_agent_tutorials\ai_recruitment_agent_team\predefined_times.json",
        "r",
    ) as file:
        predefined_data = json.load(file)

    available_times = predefined_data.get("available_times", [])
    available_times_formatted = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t in available_times]

    # Display available times in a dropdown
    selected_time = st.selectbox(
        "Select a new meeting date and time:",
        options=available_times_formatted,
        format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # Update session state if a selection is made
    if selected_time:
        if "scheduled_datetime" not in st.session_state or st.session_state["scheduled_datetime"] != selected_time:
            st.session_state["scheduled_datetime"] = selected_time
            st.success(f"Meeting updated to: {selected_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("No changes made to the meeting schedule.")

    # Display the updated date and time
    if "scheduled_datetime" in st.session_state:
        st.sidebar.info(
            f"Updated Meeting:\n"
            f"{st.session_state['scheduled_datetime'].strftime('%Y-%m-%d %H:%M:%S')}"
        )


def main() -> None:
    st.title("AI Recruitment System")

    init_session_state()
    with st.sidebar:
        st.header("Configuration")
        
        # OpenAI Configuration
        st.subheader("OpenAI Settings")
        api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state.openai_api_key, help="Get your API key from platform.openai.com")
        if api_key: st.session_state.openai_api_key = api_key
        else: st.session_state.openai_api_key = "sk-1234567890abcdef1234567890abcdef"

        st.subheader("Zoom Settings")
        zoom_account_id = st.text_input("Zoom Account ID", type="password", value=st.session_state.zoom_account_id)
        zoom_client_id = st.text_input("Zoom Client ID", type="password", value=st.session_state.zoom_client_id)
        zoom_client_secret = st.text_input("Zoom Client Secret", type="password", value=st.session_state.zoom_client_secret)
        
        st.subheader("Email Settings")
        email_sender = st.text_input("Sender Email", value=st.session_state.email_sender, help="Email address to send from")
        recruiter_email = st.text_input("Recruiter Email", value=st.session_state.recruiter_email, help="Email address to send to as a recruiter")
        email_passkey = st.text_input("Email App Password", type="password", value=st.session_state.email_passkey, help="App-specific password for email")
        company_name = st.text_input("Company Name", value=st.session_state.company_name, help="Name to use in email communications")

        if zoom_account_id:
            st.session_state.zoom_account_id = zoom_account_id
        else:
            st.session_state.zoom_account_id = "Ad5Btk3mQ2S9n39sTys4Qg"

        if zoom_client_id:
            st.session_state.zoom_client_id = zoom_client_id
        else:
            st.session_state.zoom_client_id = "6RezhEmWQ7qVGwGrUKuPMQ"
        if zoom_client_secret:
            st.session_state.zoom_client_secret = zoom_client_secret
        else:
            st.session_state.zoom_client_secret = "woLGmXOtR4PAtfPDQfoy9JWkWOUoo5lK"
        if email_sender:
            st.session_state.email_sender = email_sender
        else:
            st.session_state.email_sender = "setooproject00@gmail.com"

        if email_passkey:
            st.session_state.email_passkey = email_passkey
        else:
            st.session_state.email_passkey = "kpcxquihonbqissr"

        if company_name:
            st.session_state.company_name = company_name
        else:
            st.session_state.company_name = "Setoo"
        if recruiter_email: 
            st.session_state.recruiter_email = recruiter_email
        else:
            st.session_state.recruiter_email = "setodkar6@gmail.com"

        
        final_roles = manage_roles()
        schedule_meeting()
        st.sidebar.subheader("Manage Interview Slots")
        st.subheader("Available Slots for Self-Scheduling Interviews")

        # Define the path to the predefined times file
        predefined_times_path = r"C:\Users\Admin\python_project\awesome-llm-apps\ai_agent_tutorials\ai_recruitment_agent_team\predefined_times.json"

        # Load available times into session state
        if "available_times" not in st.session_state:
            try:
                with open(predefined_times_path, "r") as file:
                    predefined_data = json.load(file)
                    st.session_state.available_times = predefined_data.get("available_times", [])
            except FileNotFoundError:
                st.session_state.available_times = []

        # Display current available slots
        st.write("Current Available Slots:")
        for i, slot in enumerate(st.session_state.available_times):
            st.write(f"{i + 1}. {slot}")

        # Add a new slot
        with st.form("add_slot_form"):
            st.write("Add a New Slot")
            new_date = st.date_input("New Slot Date:", key="add_date")
            new_time = st.time_input("New Slot Time:", key="add_time")
            add_slot = st.form_submit_button("Add Slot")

            if add_slot and new_date and new_time:
                new_slot = f"{new_date} {new_time}"
                if new_slot not in st.session_state.available_times:
                    st.session_state.available_times.append(new_slot)
                    st.success(f"Slot {new_slot} added successfully!")
                else:
                    st.warning("This slot already exists.")

        # Remove an existing slot
        with st.form("remove_slot_form"):
            st.write("Remove an Existing Slot")
            if st.session_state.available_times:
                slot_to_remove = st.selectbox("Select Slot to Remove:", options=st.session_state.available_times, key="remove_slot")
                remove_slot = st.form_submit_button("Remove Slot")

                if remove_slot and slot_to_remove:
                    st.session_state.available_times.remove(slot_to_remove)
                    st.success(f"Slot {slot_to_remove} removed successfully!")
            else:
                st.info("No available slots to remove.")

        # Save updated slots to the JSON file
        with open(predefined_times_path, "w") as file:
            json.dump({"available_times": st.session_state.available_times}, file, indent=4)

        st.write("Changes saved successfully!")


        required_configs = {'OpenAI API Key': st.session_state.openai_api_key, 'Zoom Account ID': st.session_state.zoom_account_id,
                          'Zoom Client ID': st.session_state.zoom_client_id, 'Zoom Client Secret': st.session_state.zoom_client_secret,
                          'Email Sender': st.session_state.email_sender, 'Email Password': st.session_state.email_passkey,
                          'Company Name': st.session_state.company_name}

    missing_configs = [k for k, v in required_configs.items() if not v]
    if missing_configs:
        st.warning(f"Please configure the following in the sidebar: {', '.join(missing_configs)}")
        return

    if not st.session_state.openai_api_key:
        st.warning("Please enter your OpenAI API key in the sidebar to continue.")
        return

    role = st.selectbox("Select the role you're applying for:", list(final_roles.keys()))
    with st.expander("View Required Skills", expanded=True): st.markdown(final_roles[role])

    # Add a "New Application" button before the resume upload
    if st.button("📝 New Application"):
        # Clear only the application-related states
        keys_to_clear = ['resume_text', 'analysis_complete', 'is_selected', 'candidate_email', 'current_pdf']
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = None if key == 'current_pdf' else ""
        st.rerun()

    resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"], key="resume_uploader")
    if resume_file is not None and resume_file != st.session_state.get('current_pdf'):
        st.session_state.current_pdf = resume_file
        st.session_state.resume_text = ""
        st.session_state.analysis_complete = False
        st.session_state.is_selected = False
        st.rerun()

    if resume_file:
        st.subheader("Uploaded Resume")
        col1, col2 = st.columns([4, 1])
        
        with col1:
            import tempfile, os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_file_path = tmp_file.name
            resume_file.seek(0)
            try: pdf_viewer(tmp_file_path)
            finally: os.unlink(tmp_file_path)
        
        with col2:
            st.download_button(label="📥 Download", data=resume_file, file_name=resume_file.name, mime="application/pdf")
        # Process the resume text
        if not st.session_state.resume_text:
            with st.spinner("Processing your resume..."):
                resume_text = extract_text_from_pdf(resume_file)
                if resume_text:
                    st.session_state.resume_text = resume_text
                    st.success("Resume processed successfully!")
                else:
                    st.error("Could not process the PDF. Please try again.")

    # Email input with session state
    email_can = st.text_input(
        "Candidate's email address",
        value=st.session_state.candidate_email,
        key="email_input"
    )
    if email_can :
        st.session_state.candidate_email = email_can
    else:
        st.session_state.candidate_email = "setodkar06@gmail.com"

    # Analysis and next steps
    if st.session_state.resume_text and st.session_state.candidate_email and not st.session_state.analysis_complete:
        if st.button("Analyze Resume"):
            with st.spinner("Analyzing your resume..."):
                
                if True :
                    print("DEBUG: Starting resume analysis")
                    is_selected, feedback = analyze_resume(
                        st.session_state.resume_text,
                        role
                    )
                    print(f"DEBUG: Analysis complete - Selected: {is_selected}, Feedback: {feedback}")

                    if is_selected:
                        st.success("Congratulations! Your skills match our requirements.")
                        st.session_state.analysis_complete = True
                        st.session_state.is_selected = True
                        st.rerun()
                    else:
                        st.warning("Unfortunately, your skills don't match our requirements.")
                        st.write(f"Feedback: {feedback}")
                        
                        # Send rejection email
                        with st.spinner("Sending feedback email..."):
                            try:
                                send_rejection_email(st.session_state.get('email_sender'),
                                                     st.session_state.get('email_passkey'), 
                                                     st.session_state.get('candidate_email'),
                                                     role, 
                                                     st.session_state.get('company_name'),
                                                     )
                                st.info("We've sent you an email with detailed feedback.")
                            except Exception as e:
                                logger.error(f"Error sending rejection email: {e}")
                                st.error("Could not send feedback email. Please try again.")

    if st.session_state.get('analysis_complete') and st.session_state.get('is_selected', False) and not st.session_state.get('proceed_app'):
        st.success("Congratulations! Your skills match our requirements.")
        st.info("Click 'Proceed with Application' to continue with the interview process.")
        
        if st.button("Proceed with Application", key="proceed_button"):
            print("DEBUG: Proceed button clicked")  # Debug
            with st.spinner("🔄 Processing your application..."):
                try:
                    # 3. Send selection email
                    with st.status("📧 Sending confirmation email...", expanded=True) as status:
                        print(f"DEBUG: Attempting to send email to {st.session_state.candidate_email}")  # Debug
                        send_selection_email(
                           st.session_state.get('email_sender'),
                           st.session_state.get('email_passkey'),
                           st.session_state.get('candidate_email'), 
                           role, 
                           st.session_state.get('company_name'))
                        print("DEBUG: Email sent successfully")  # Debug
                        status.update(label="✅ Confirmation email sent!")

                    st.session_state.proceed_app = True
                    
                    # 4. Schedule interview
                    with st.status("📅 Scheduling interview...", expanded=True):
                        print("DEBUG: Attempting to schedule interview")  # Debug

                    st.rerun()

                except Exception as e:
                    print(f"DEBUG: Error occurred: {str(e)}")  # Debug
                    print(f"DEBUG: Error type: {type(e)}")  # Debug
                    import traceback
                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")  # Debug
                    st.error(f"An error occurred: {str(e)}")
                    st.error("Please try again or contact support.")
                    

    if not st.session_state.get('no_button') and st.session_state.get('proceed_app'):
        st.success("Confimation email sent successfully!")
        st.info("Schedule interview time out of given time!")
        st.session_state.time_change_requested = ask_for_time_change()
        st.session_state.check_again = True

    if st.session_state.get('time_change_requested') and not st.session_state.get('time_and_date'):
        st.session_state.check_it = True
        update_meeting_schedule() 
    else:
        st.session_state.check_it = True


    if st.session_state.get('check_it') and st.session_state.get('check_again') and not st.session_state.get('fragment'):
        if st.button("Proceed with Schedule", key="schedule_button"):
            st.session_state.no_button = True
            st.session_state.time_and_date = True
            schedule_interview(
                st.session_state.get('zoom_account_id'),
                st.session_state.get('zoom_client_id'),
                st.session_state.get('zoom_client_secret'),
                st.session_state.get('email_sender'),
                st.session_state.get('email_passkey'),
                st.session_state.get('candidate_email'),
                st.session_state.get('recruiter_email'),
                role,
                st.session_state.get('company_name'),
                "UTC"
            )
            st.session_state.fragment = True
            st.rerun()

    if st.session_state.get('fragment'):
        st.success("Interview scheduled successfully! Check your email for details.")
        st.info("Interview scheduled and email sent successfully.")
        st.info("Take assessment test!")
        print("DEBUG: All processes completed successfully")  # Debug
        st.success("""
            🎉 Application Successfully Processed!
            
            Please check your email for:
            1. Selection confirmation ✅
            2. Interview details with Zoom link 🔗
            
            Next steps:
            1. Review the role requirements
            2. Prepare for your technical interview
            3. Join the interview 5 minutes early
        """)


    # Reset button
    if st.sidebar.button("Reset Application"):
        for key in st.session_state.keys():
            if key != 'openai_api_key':
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()