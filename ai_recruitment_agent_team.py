from typing import Literal, Tuple, Dict, Optional
import os
import time
import json
import smtplib
import requests
import PyPDF2
from datetime import datetime, timedelta
import pytz
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


import streamlit as st
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.email import EmailTools
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
ROLE_REQUIREMENTS: Dict[str, str] = {
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
    role: Literal["ai_ml_engineer", "frontend_engineer", "backend_engineer"]
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


def send_selection_email( sender_email, sender_password, receiver_email) -> None:
        """Send an email with the given subject and body."""
        msg = MIMEText('this is the body of acceptance mail')
        msg["Subject"] = 'you are accepted for role'
        msg["From"] = sender_email
        msg["To"] = receiver_email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
    


def send_rejection_email(sender_email, sender_password, receiver_email) -> None:
      """Send an email with the given subject and body."""
      msg = MIMEText('this is the body of rejection mail')
      msg["Subject"] = 'you got rejected'
      msg["From"] = sender_email
      msg["To"] = receiver_email
      with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
    


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def schedule_interview(zoom_acc_id, zoom_client_id, zoom_secret, sender_email, sender_password, receiver_email, role: str) -> None:
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
        subject = "Interview Scheduled"
        body = f"""\
        Dear Candidate,

        You have an interview scheduled for the role of {role}.

        Meeting Details:
        Link: {meeting_link}
        Date: {meeting_time.strftime('%Y-%m-%d')}
        Time: {meeting_time.strftime('%H:%M:%S')} UTC

        Best regards,
        Hiring Team
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

    missing_configs = [k for k, v in required_configs.items() if not v]
    if missing_configs:
        st.warning(f"Please configure the following in the sidebar: {', '.join(missing_configs)}")
        return

    if not st.session_state.openai_api_key:
        st.warning("Please enter your OpenAI API key in the sidebar to continue.")
        return

    role = st.selectbox("Select the role you're applying for:", ["ai_ml_engineer", "frontend_engineer", "backend_engineer"])
    with st.expander("View Required Skills", expanded=True): st.markdown(ROLE_REQUIREMENTS[role])

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
                                send_rejection_email(st.session_state.get('email_sender'),st.session_state.get('email_passkey'), st.session_state.get('candidate_email'))
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
                           st.session_state.get('email_sender'),st.session_state.get('email_passkey'), st.session_state.get('candidate_email'))
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
                            'Software Enginner'

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