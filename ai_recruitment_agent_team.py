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
        'candidate_email': "", 'openai_api_key': "", 'resume_text': "", 'analysis_complete': False,
        'is_selected': False, 'zoom_account_id': "", 'zoom_client_id': "", 'zoom_client_secret': "",
        'email_sender': "", 'email_passkey': "", 'company_name': "", 'current_pdf': None
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

def schedule_interview(zoom_acc_id, zoom_client_id, zoom_secret, sender_email, sender_password, receiver_email, role: str, company) -> None:
    try:
        # Step 1: Get Zoom OAuth token
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

        # Step 2: Schedule a Zoom meeting
        zoom_meeting_url = "https://api.zoom.us/v2/users/me/meetings"
        meeting_time = datetime.utcnow() + timedelta(days=1)  # 24 hours from now
        meeting_time_iso = meeting_time.strftime("%Y-%m-%dT%H:%M:%SZ")  # ISO 8601 format
        
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

        # Step 3: Send email with meeting details
        subject = f"Interview Scheduled for {role} at {company}"
        body = f"""
        Dear Candidate,

        We are pleased to inform you that your interview for the {role} role at {company} has been scheduled.

        Meeting Details:
        - Link: {meeting_link}
        - Date: {meeting_time.strftime('%Y-%m-%d')}
        - Time: {meeting_time.strftime('%H:%M:%S')} UTC

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

        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = receiver_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

        st.success("Interview scheduled successfully! Check your email for details.")
        logger.info("Interview scheduled and email sent successfully.")

    except Exception as e:
        logger.error(f"Error scheduling interview: {str(e)}")
        st.error("Unable to schedule interview. Please try again.")

def main() -> None:
    st.title("AI Recruitment System")

    init_session_state()
    with st.sidebar:
        st.header("Configuration")
        
        # OpenAI Configuration
        st.subheader("OpenAI Settings")
        api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state.openai_api_key, help="Get your API key from platform.openai.com")
        if api_key: st.session_state.openai_api_key = api_key

        st.subheader("Zoom Settings")
        zoom_account_id = st.text_input("Zoom Account ID", type="password", value=st.session_state.zoom_account_id)
        zoom_client_id = st.text_input("Zoom Client ID", type="password", value=st.session_state.zoom_client_id)
        zoom_client_secret = st.text_input("Zoom Client Secret", type="password", value=st.session_state.zoom_client_secret)
        
        st.subheader("Email Settings")
        email_sender = st.text_input("Sender Email", value=st.session_state.email_sender, help="Email address to send from")
        email_passkey = st.text_input("Email App Password", type="password", value=st.session_state.email_passkey, help="App-specific password for email")
        company_name = st.text_input("Company Name", value=st.session_state.company_name, help="Name to use in email communications")

        if zoom_account_id: st.session_state.zoom_account_id = zoom_account_id
        if zoom_client_id: st.session_state.zoom_client_id = zoom_client_id
        if zoom_client_secret: st.session_state.zoom_client_secret = zoom_client_secret
        if email_sender: st.session_state.email_sender = email_sender
        if email_passkey: st.session_state.email_passkey = email_passkey
        if company_name: st.session_state.company_name = company_name

        required_configs = {'OpenAI API Key': st.session_state.openai_api_key, 'Zoom Account ID': st.session_state.zoom_account_id,
                          'Zoom Client ID': st.session_state.zoom_client_id, 'Zoom Client Secret': st.session_state.zoom_client_secret,
                          'Email Sender': st.session_state.email_sender, 'Email Password': st.session_state.email_passkey,
                          'Company Name': st.session_state.company_name}
##########################################################################################################################################
        
        final_roles = manage_roles()
        schedule_meeting()
#########################################################################################################################################
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
    email = st.text_input(
        "Candidate's email address",
        value=st.session_state.candidate_email,
        key="email_input"
    )
    st.session_state.candidate_email = email

    # Analysis and next steps
    if st.session_state.resume_text and email and not st.session_state.analysis_complete:
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
                                                     st.session_state.get('company_name'))
                                st.info("We've sent you an email with detailed feedback.")
                            except Exception as e:
                                logger.error(f"Error sending rejection email: {e}")
                                st.error("Could not send feedback email. Please try again.")

    if st.session_state.get('analysis_complete') and st.session_state.get('is_selected', False):
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

                    # 4. Schedule interview
                    with st.status("📅 Scheduling interview...", expanded=True) as status:
                        print("DEBUG: Attempting to schedule interview")  # Debug
                        schedule_interview(
                            st.session_state.get('zoom_account_id'),
                            st.session_state.get('zoom_client_id'),
                            st.session_state.get('zoom_client_secret'),
                            st.session_state.get('email_sender'),
                            st.session_state.get('email_passkey'),
                            st.session_state.get('candidate_email'),
                            role,
                            st.session_state.get('company_name')

                        )
                        print("DEBUG: Interview scheduled successfully")  # Debug
                        status.update(label="✅ Interview scheduled!")

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

                except Exception as e:
                    print(f"DEBUG: Error occurred: {str(e)}")  # Debug
                    print(f"DEBUG: Error type: {type(e)}")  # Debug
                    import traceback
                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")  # Debug
                    st.error(f"An error occurred: {str(e)}")
                    st.error("Please try again or contact support.")

    # Reset button
    if st.sidebar.button("Reset Application"):
        for key in st.session_state.keys():
            if key != 'openai_api_key':
                del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()