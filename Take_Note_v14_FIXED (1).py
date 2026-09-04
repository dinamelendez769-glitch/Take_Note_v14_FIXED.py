import streamlit as st
import time
import random
import json
import os
import re
import tempfile

# ==========================================
# PAGE CONFIG & STATE INITIALIZATION
# ==========================================
# Streamlit requires page configuration before other Streamlit commands.
st.set_page_config(
    page_title="Take Note: Master Recorder Studio",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check for incoming sync parameters and rhythm score from local JS Metronome & DAW.
sync_bpm = None
sync_pattern = None
score_param = None

if hasattr(st, "query_params"):
    if "sync_bpm" in st.query_params:
        sync_bpm = st.query_params["sync_bpm"]
    if "sync_pattern" in st.query_params:
        sync_pattern = st.query_params["sync_pattern"]
    if "rhythm_score" in st.query_params:
        score_param = st.query_params["rhythm_score"]
    try:
        st.query_params.clear()
    except Exception:
        pass
elif hasattr(st, "experimental_get_query_params"):
    q_params = st.experimental_get_query_params()
    if "sync_bpm" in q_params:
        sync_bpm = q_params["sync_bpm"][0]
    if "sync_pattern" in q_params:
        sync_pattern = q_params["sync_pattern"][0]
    if "rhythm_score" in q_params:
        score_param = q_params["rhythm_score"][0]
    try:
        st.experimental_set_query_params()
    except Exception:
        pass

PROJECTS_FILE = os.environ.get(
    "TAKE_NOTE_PROJECTS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "take_note_projects.json")
)

PROJECT_LANES = ("kick", "snare", "hat", "bass")
PROJECT_KEYS = [
    "C Major", "A Minor", "G Major", "E Minor", "F Major", "D Minor",
    "D Major", "B Minor", "A Major", "F# Minor", "E Major", "C# Minor"
]
PROJECT_GENRES = ["Hip-Hop", "R&B", "Pop", "EDM", "Lo-Fi", "Cinematic"]
PROJECT_MOODS = ["Chill", "Dark", "Melancholic", "Energetic", "Aggressive"]

def validate_pattern(pattern):
    if not isinstance(pattern, dict):
        return False
    return all(
        isinstance(pattern.get(lane), list)
        and len(pattern[lane]) == 16
        and all(isinstance(x, int) and x in (0, 1) for x in pattern[lane])
        for lane in PROJECT_LANES
    )

def sanitize_project(project):
    if not isinstance(project, dict):
        return None
    try:
        bpm = max(60, min(200, int(project.get("bpm", 120))))
    except (TypeError, ValueError):
        bpm = 120
    key = project.get("key", "C Major")
    genre = project.get("genre", "Hip-Hop")
    mood = project.get("mood", "Chill")
    pattern = project.get("pattern")
    if key not in PROJECT_KEYS:
        key = "C Major"
    if genre not in PROJECT_GENRES:
        genre = "Hip-Hop"
    if mood not in PROJECT_MOODS:
        mood = "Chill"
    if not validate_pattern(pattern):
        return None
    return {"bpm": bpm, "key": key, "genre": genre, "mood": mood, "pattern": pattern}

def sync_project_widget_state():
    project = st.session_state.project
    st.session_state["bpm_slider"] = project["bpm"]
    st.session_state["key_selectbox"] = project["key"]
    st.session_state["genre_selectbox"] = project["genre"]
    st.session_state["mood_slider"] = project["mood"]

def load_projects_from_file():
    if not os.path.exists(PROJECTS_FILE):
        return []
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError) as e:
        st.error(f"⚠️ Failed to load local projects from storage disk: {e}")
        return []

def save_projects_to_file(projects):
    """Atomically replace the project file so interrupted writes do not corrupt JSON."""
    directory = os.path.dirname(PROJECTS_FILE) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".take_note_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(projects, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, PROJECTS_FILE)
            return True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except OSError as e:
        st.error(f"⚠️ Failed to save project metadata to storage disk: {e}")
        return False

# Initialize Session State
if "mode" not in st.session_state:
    st.session_state.mode = "intro"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "email" not in st.session_state:
    st.session_state.email = ""
if "lyrics" not in st.session_state:
    st.session_state.lyrics = ""
if "saved_projects" not in st.session_state:
    st.session_state.saved_projects = load_projects_from_file()
if "lessons_completed" not in st.session_state:
    st.session_state.lessons_completed = ["Rhythm Basics", "Intro to Scales"]
if "rhythm_scores" not in st.session_state:
    st.session_state.rhythm_scores = [85, 92, 88]
if "generation_id" not in st.session_state:
    st.session_state.generation_id = 0

# Robust chat history initialization
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Welcome back! I am Lyric, your AI music producer, tutor, and coach. Ask me questions about mixing, song structure, or music theory to get started."}
    ]

# Default values for adjustable project widgets to support save/load overrides
if "project" not in st.session_state:
    st.session_state.project = {
        "bpm": 120,
        "key": "C Major",
        "genre": "Hip-Hop",
        "mood": "Chill",
        "pattern": {
            "kick":  [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hat":   [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "bass":  [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1]
        }
    }

# Apply queued project changes before widgets render so loaded/synced values
# are not overwritten by Streamlit's persistent widget state.
if "pending_project" in st.session_state:
    pending = sanitize_project(st.session_state.pop("pending_project"))
    if pending:
        st.session_state.project.update(pending)
        st.session_state.generation_id += 1
        sync_project_widget_state()

if sync_bpm is not None:
    try:
        st.session_state.project["bpm"] = max(60, min(200, int(sync_bpm)))
    except (TypeError, ValueError):
        st.error("⚠️ Ignored invalid BPM received from the DAW.")

if sync_pattern is not None:
    try:
        parsed_pattern = json.loads(sync_pattern)
        if validate_pattern(parsed_pattern):
            st.session_state.project["pattern"] = parsed_pattern
            st.toast("🎵 DAW sequencer grid synchronized with your portal!", icon="🎵")
        else:
            st.error("⚠️ Rejected malformed pattern sequence from the DAW.")
    except (TypeError, json.JSONDecodeError):
        st.error("⚠️ Could not parse the sequencer pattern received from the DAW.")

if sync_bpm is not None or sync_pattern is not None:
    sync_project_widget_state()

if score_param is not None:
    try:
        score = max(0, min(100, int(score_param)))
        if score not in st.session_state.rhythm_scores:
            st.session_state.rhythm_scores.append(score)
    except (TypeError, ValueError):
        st.error("⚠️ Ignored invalid rhythm score received from the trainer.")

if st.session_state.get("loaded_project_notice"):
    st.success(f"Project '{st.session_state.pop('loaded_project_notice')}' loaded successfully.")

if "bpm_slider" not in st.session_state:
    sync_project_widget_state()

custom_css = """
<style>
/* Universal Dark UI styling */
.stApp {
    background-color: #04060a;
    color: #E2E8F0;
    font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}

/* Hide standard Streamlit header/footer */
header, footer {
    visibility: hidden !important;
}

/* Intro Screen Styling */
.intro-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 85vh;
    text-align: center;
    background: radial-gradient(circle at center, #0F172A 0%, #020617 70%);
}

.intro-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 3.5rem;
    font-weight: 800;
    letter-spacing: 0.35rem;
    text-transform: uppercase;
    background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
    filter: drop-shadow(0 0 15px rgba(56, 189, 248, 0.3));
}

.intro-subtitle {
    font-size: 1.1rem;
    font-weight: 300;
    color: #94A3B8;
    letter-spacing: 0.15rem;
    margin-bottom: 3rem;
}

/* Pulsing Glowing Arc-Reactor Ring */
.orb-wrapper {
    position: relative;
    width: 220px;
    height: 220px;
    margin-bottom: 4rem;
}

.glowing-orb {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 140px;
    height: 140px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.4) 0%, rgba(56, 189, 248, 0) 70%);
    box-shadow: 
        0 0 40px 10px rgba(56, 189, 248, 0.5),
        0 0 80px 20px rgba(129, 140, 248, 0.3),
        inset 0 0 20px rgba(255, 255, 255, 0.6);
    animation: pulse 3s infinite ease-in-out;
}

.outer-ring {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 190px;
    height: 190px;
    border-radius: 50%;
    border: 2px dashed rgba(56, 189, 248, 0.6);
    animation: rotate-clockwise 20s linear infinite;
}

.inner-ring {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 165px;
    height: 165px;
    border-radius: 50%;
    border: 1px solid rgba(129, 140, 248, 0.4);
    animation: rotate-counter 12s linear infinite;
}

@keyframes pulse {
    0% { transform: translate(-50%, -50%) scale(0.95); opacity: 0.7; filter: drop-shadow(0 0 20px rgba(56, 189, 248, 0.4)); }
    50% { transform: translate(-50%, -50%) scale(1.08); opacity: 1; filter: drop-shadow(0 0 45px rgba(56, 189, 248, 0.8)); }
    100% { transform: translate(-50%, -50%) scale(0.95); opacity: 0.7; filter: drop-shadow(0 0 20px rgba(56, 189, 248, 0.4)); }
}

@keyframes rotate-clockwise {
    from { transform: translate(-50%, -50%) rotate(0deg); }
    to { transform: translate(-50%, -50%) rotate(360deg); }
}

@keyframes rotate-counter {
    from { transform: translate(-50%, -50%) rotate(360deg); }
    to { transform: translate(-50%, -50%) rotate(0deg); }
}

.header-bar {
    padding: 1rem 1.5rem;
    background: linear-gradient(90deg, #0D0E12 0%, #151922 100%);
    border-bottom: 1px solid #1E293B;
    border-radius: 12px;
    margin-bottom: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.app-logo {
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: 0.15rem;
    text-transform: uppercase;
    background: linear-gradient(90deg, #38BDF8 0%, #818CF8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# PHASE 1: THE LYRIC INTRO SCREEN
# ==========================================
if st.session_state.mode == "intro":
    st.markdown('<div class="intro-container">', unsafe_allow_html=True)
    
    # Glowing Orb
    st.markdown("""
        <div class="orb-wrapper">
            <div class="outer-ring"></div>
            <div class="inner-ring"></div>
            <div class="glowing-orb"></div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="intro-title">Take Note</h1>', unsafe_allow_html=True)
    st.markdown('<p class="intro-subtitle">AI MUSIC PRODUCTION, COACHING & LEARNING ECOSYSTEM</p>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="max-width: 600px; margin: 0 auto 3rem auto; color: #94A3B8; font-size: 1.1rem; line-height: 1.6rem; font-weight: 300;">
        "Hello, I am Lyric. I am your co-producer, instructor, and coach. Let's fire up a real Web Audio workspace on your machine to play, record, and synthesize beats."
    </div>
    """, unsafe_allow_html=True)
    
    # Enter Button
    col_btn_l, col_btn_c, col_btn_r = st.columns([2, 1, 2])
    with col_btn_c:
        if st.button("ENTER STUDIO", key="enter_studio_btn", use_container_width=True):
            st.session_state.mode = "studio"
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PHASE 2: THE TAKE NOTE STUDIO & REAL ENGINE
# ==========================================
else:
    # Top Header
    st.markdown("""
        <div class="header-bar">
            <div class="app-logo">TAKE NOTE STUDIO</div>
            <div style="display: flex; gap: 1.5rem; align-items: center; color: #94A3B8;">
                <span style="font-size: 0.9rem; color: #38BDF8; font-weight: bold;">⚡ WEB AUDIO ENGINE READY</span>
                <span style="font-size: 0.9rem; color: #10B981;">● AUDIO ENGINE: READY</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([5, 2])

    with left_col:
        tab_studio, tab_academy, tab_progress = st.tabs([
            "🎛️ REAL-TIME DAW STUDIO", 
            "🎓 LYRIC MUSIC ACADEMY", 
            "📈 PROGRESS & METRICS"
        ])

        with tab_studio:
            st.markdown("### 🎚️ MULTI-TRACK AUDIO ENGINE & BEAT STEP SEQUENCER")
            st.markdown("This section runs a browser-based **Web Audio API mixer**. Toggle grids, record voice, sync tracks, and export uncompressed WAV mixes.")

            # Beat Parameter Panel (Feature 3)
            with st.expander("🎚️ PROJECT CONFIGURATOR & STYLE REFERENCES", expanded=True):
                col_param1, col_param2, col_param3 = st.columns([2, 2, 3])
                
                with col_param1:
                    bpm = st.slider("BPM (Tempo)", min_value=60, max_value=200, value=st.session_state.project["bpm"], step=1, key="bpm_slider")
                    st.session_state.project["bpm"] = bpm
                    
                    key_sig = st.selectbox("Musical Key", [
                        "C Major", "A Minor", "G Major", "E Minor", "F Major", "D Minor",
                        "D Major", "B Minor", "A Major", "F# Minor", "E Major", "C# Minor"
                    ], index=[
                        "C Major", "A Minor", "G Major", "E Minor", "F Major", "D Minor",
                        "D Major", "B Minor", "A Major", "F# Minor", "E Major", "C# Minor"
                    ].index(st.session_state.project["key"]), key="key_selectbox")
                    st.session_state.project["key"] = key_sig
                
                with col_param2:
                    genre = st.selectbox("Genre", ["Hip-Hop", "R&B", "Pop", "EDM", "Lo-Fi", "Cinematic"], 
                                         index=["Hip-Hop", "R&B", "Pop", "EDM", "Lo-Fi", "Cinematic"].index(st.session_state.project["genre"]), key="genre_selectbox")
                    st.session_state.project["genre"] = genre
                    
                    mood = st.select_slider("Mood & Tone", options=["Chill", "Dark", "Melancholic", "Energetic", "Aggressive"], value=st.session_state.project["mood"], key="mood_slider")
                    st.session_state.project["mood"] = mood
                
                with col_param3:
                    st.markdown("<p style='font-weight:600; font-size:0.9rem; margin-bottom:0.25rem;'>Genre & Production Style Mapper (Feature 4)</p>", unsafe_allow_html=True)
                    ref_input = st.text_input(
                        "Search production style or artist character (e.g., Billie Eilish, Hans Zimmer, Daft Punk)...", 
                        placeholder="e.g., Billie Eilish - Bad Guy, Metro Boomin style",
                        key="style_ref_input"
                    )
                    
                    # Apply a style reference only when the input changes.
                    # This prevents every Streamlit rerun from overwriting manual edits.
                    if ref_input and ref_input.strip() != st.session_state.get("last_applied_style_ref", ""):
                        match_ref = ref_input.strip().lower()
                        extracted = None
                        for db_key, db_data in STYLE_DATABASE.items():
                            if db_key in match_ref:
                                extracted = db_data
                                break
                        if not extracted:
                            extracted = extract_procedural_fingerprint(ref_input)

                        if extracted:
                            st.session_state.project["bpm"] = max(60, min(200, int(extracted["bpm"])))
                            st.session_state.project["key"] = extracted["key"]
                            st.session_state.project["genre"] = extracted["genre"]
                            st.session_state.project["mood"] = extracted["mood"]
                            st.session_state.project["pattern"] = extracted["pattern"]
                            st.session_state.last_applied_style_ref = ref_input.strip()
                            st.session_state.style_notice = extracted
                            st.session_state.pending_project = dict(st.session_state.project)
                            st.rerun()

                    if st.session_state.get("style_notice"):
                        notice = st.session_state.pop("style_notice")
                        st.success(
                            f"✨ **Style Mapper Configured:** Scale: {notice['key']} | "
                            f"BPM: {notice['bpm']} | Genre: {notice['genre']}"
                        )
                        st.info(notice["chat_comment"])
                        if not st.session_state.chat_history or st.session_state.chat_history[-1]["content"] != notice["chat_comment"]:
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": notice["chat_comment"]
                            })

            # Trigger Actions
            col_act1, col_act2, col_act3 = st.columns([1, 1, 1])
            with col_act1:
                # AI Beat Generator (Feature 2 & 7) with dynamic Python pattern generator
                if st.button("🔥 GENERATE AI BEAT", key="gen_beat_btn", use_container_width=True):
                    with st.spinner("Lyric is carving out the drum sequence and synthesizing bassline..."):
                        time.sleep(1.2)
                        
                        # If reference search input is active, it has already injected a pattern!
                        # Otherwise, compile a standard procedural genre block.
                        if st.session_state.get("last_applied_style_ref") == st.session_state.style_ref_input.strip():
                            # Keep the currently applied style-reference pattern.
                            pass
                        elif genre == "Hip-Hop":
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                "hat": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                                "bass": [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0]
                            }
                        elif genre == "R&B":
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
                                "hat": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                                "bass": [1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0]
                            }
                        elif genre == "Pop":
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                "hat": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                                "bass": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0]
                            }
                        elif genre == "EDM":
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                "hat": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                                "bass": [1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0]
                            }
                        elif genre == "Lo-Fi":
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                "hat": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                                "bass": [1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
                            }
                        else:  # Cinematic
                            st.session_state.project["pattern"] = {
                                "kick": [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
                                "snare": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
                                "hat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                "bass": [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]
                            }
                        
                        st.session_state.generation_id += 1
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"I have loaded a custom drum pattern and synth outline based on your selected **{genre}** genre! The sequence has been calibrated for your {mood.lower()} atmosphere in **{key_sig}** at **{bpm} BPM**."
                        })
                        st.rerun()
            with col_act2:
                # Smart Lyric Generator (Feature 5 & User Critique 2)
                if st.button("✍️ SMART LYRIC GENERATOR", key="gen_lyrics_btn", use_container_width=True):
                    with st.spinner("Drafting rhythmic lyrics matched to the beat's vibe..."):
                        time.sleep(1.0)
                        templates = {
                            "Hip-Hop": f"[Verse 1]\nYeah, standard beat at {bpm} pacing,\nNo time to waste, shadows we're chasing.\nLocked in the key of {key_sig} dreaming,\nWhile the studio lights are neon-gleaming.\n\n[Chorus]\nTake notes, we elevate,\nLyric on the beat, we recreate.",
                            "R&B": f"[Verse 1]\nLate nights under neon blue,\nThinking 'bout the chords that lead to you.\n{key_sig} matches how I feel,\nThis rhythm makes the story real.\n\n[Chorus]\nOh, we take notes on the vibe,\nKeep the rhythm alive.",
                            "Pop": f"[Verse 1]\nStep into the lights, feel the pulse begin,\n{bpm} beats per minute under my skin.\nNo looking back, we're on the run,\nSinging our song under the artificial sun.\n\n[Chorus]\nTake a note, make it loud,\nStand out in the crowd.",
                            "EDM": f"[Verse 1]\nSynthetic waves, pulse of the crowd,\nBass drops heavy, play it loud.\nIn the key of {key_sig} we soar,\nOn the floor, we're wanting more.\n\n[Chorus]\nOh, feel the voltage rise,\nUnder absolute neon skies.",
                            "Lo-Fi": f"[Verse 1]\nRaindrops tapping on the glass pane,\nChill chords washing away the strain.\n{bpm} BPM, a dusty vinyl spin,\nLetting the late night story begin.\n\n[Chorus]\nYeah, a simple tape delay,\nLetting the worries drift away.",
                            "Cinematic": f"[Verse 1]\nOrchestral strings swell in the dark,\nA lingering shadow, a sudden spark.\n{key_sig} paints the cinematic scene,\nA widescreen epic, a vivid dream.\n\n[Chorus]\nAnd the music tells the story,\nClimbing high to reach the glory."
                        }
                        st.session_state.lyrics = templates.get(genre, f"[Verse 1]\nFlowing in {key_sig} with a {mood.lower()} tone,\nCrafting these notes on my own.\nEvery drum hit speaks to the core,\nEvery melody opening the door.")
                        st.session_state.chat_history.append({
                            "role": "assistant", 
                            "content": f"I drafted custom rhythmic lyrics aligned with your {mood.lower()} {genre} vibe using the Smart Lyric Generator. The verses are set up to flow beautifully over the 4/4 drum structure."
                        })
                        st.rerun()
            with col_act3:
                # Project Studio Controls (Feature 6)
                if st.button("👥 SYNC PROJECT TO PROFILE", key="sync_profile_btn", use_container_width=True):
                    if st.session_state.logged_in:
                        st.success(f"Successfully synced session configuration with {st.session_state.email}!")
                    else:
                        st.error("🔒 Profile synchronization requires account login. Switch to the Progress & Metrics tab!")

            # Prepare JSON representation of the pattern to inject into Web Audio DAW
            pattern_json = json.dumps(st.session_state.project["pattern"])
            gen_id = st.session_state.generation_id

            # Project persistent local JSON manager (Requirement 4)
            with st.expander("📂 PERSISTENT PROJECT FILE STORAGE (SAVE / LOAD)", expanded=True):
                col_save_proj, col_load_proj = st.columns(2)
                with col_save_proj:
                    st.write("**Save current project to sandbox disk:**")
                    proj_name = st.text_input("Enter unique project title:", value=f"My Beat - {st.session_state.project['genre']}")
                    if st.button("💾 SAVE PROJECT TO DISK", use_container_width=True):
                        if not validate_pattern(st.session_state.project.get("pattern")):
                            st.error("⚠️ Current sequencer pattern is invalid and cannot be saved.")
                        else:
                            # Load current disk list
                            disk_projects = load_projects_from_file()
                            new_proj_entry = {
                                "name": proj_name,
                                "bpm": st.session_state.project["bpm"],
                                "key": st.session_state.project["key"],
                                "genre": st.session_state.project["genre"],
                                "mood": st.session_state.project["mood"],
                                "lyrics": st.session_state.lyrics,
                                "chat_history": st.session_state.chat_history,
                                "pattern": st.session_state.project["pattern"],
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            # Overwrite if exists, otherwise append
                            disk_projects = [p for p in disk_projects if p["name"] != proj_name]
                            disk_projects.append(new_proj_entry)
                            if save_projects_to_file(disk_projects):
                                st.session_state.saved_projects = disk_projects
                                st.success(f"Project '{proj_name}' saved successfully.")
                                st.rerun()

                with col_load_proj:
                    st.write("**Load project from sandbox disk:**")
                    disk_projects = load_projects_from_file()
                    st.session_state.saved_projects = disk_projects
                    if disk_projects:
                        proj_to_load = st.selectbox("Select project to load:", [p["name"] for p in disk_projects])
                        if st.button("📂 LOAD SELECTED PROJECT", use_container_width=True):
                            p_match = next((p for p in disk_projects if p["name"] == proj_to_load), None)
                            if p_match:
                                loaded_pattern = p_match.get("pattern", p_match.get("sequencer_pattern"))
                                loaded_project = sanitize_project({
                                    "bpm": p_match.get("bpm", 120),
                                    "key": p_match.get("key", "C Major"),
                                    "genre": p_match.get("genre", "Hip-Hop"),
                                    "mood": p_match.get("mood", "Chill"),
                                    "pattern": loaded_pattern
                                })
                                if loaded_project:
                                    st.session_state.pending_project = loaded_project
                                    st.session_state.lyrics = p_match.get("lyrics", "")
                                    st.session_state.chat_history = p_match.get("chat_history", st.session_state.chat_history)
                                    st.session_state.loaded_project_notice = proj_to_load
                                    st.rerun()
                                else:
                                    st.error("⚠️ The selected project contains an invalid sequencer pattern and was not loaded.")
                    else:
                        st.info("No saved projects found on sandbox disk. Type a name to save above!")

            # The entire real audio engine is embedded as a single robust HTML iframe
            # to bypass Streamlit latency issues and run real-time audio contexts.
            daw_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <style>
                body {{
                  background-color: #0A0D14;
                  color: #E2E8F0;
                  font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                  margin: 0;
                  padding: 15px;
                }}
                .daw-container {{
                  display: flex;
                  flex-direction: column;
                  gap: 15px;
                }}
                .panel {{
                  background-color: #111622;
                  border: 1px solid #1F293D;
                  border-radius: 12px;
                  padding: 15px;
                }}
                .panel-title {{
                  font-size: 1rem;
                  font-weight: 700;
                  letter-spacing: 0.05rem;
                  color: #38BDF8;
                  margin-bottom: 12px;
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                }}
                /* Track Layouts */
                .mixer-row {{
                  display: grid;
                  grid-template-columns: 150px 1fr 220px;
                  align-items: center;
                  gap: 15px;
                  padding: 10px;
                  border-radius: 8px;
                  background-color: #0E121A;
                  margin-bottom: 8px;
                }}
                .track-name {{ font-weight: 600; font-size: 0.9rem; }}
                .track-m {{ border-left: 4px solid #38BDF8; }}
                .track-b {{ border-left: 4px solid #818CF8; }}
                .track-d {{ border-left: 4px solid #F43F5E; }}
                .track-v {{ border-left: 4px solid #10B981; }}

                /* Waveform Canvas */
                canvas {{
                  width: 100%;
                  height: 40px;
                  background-color: #05070A;
                  border-radius: 6px;
                }}
                .ctrl-btns {{
                  display: flex;
                  gap: 5px;
                }}
                button {{
                  background: #1E293B;
                  border: 1px solid #334155;
                  color: #ffffff;
                  padding: 6px 12px;
                  font-size: 0.8rem;
                  font-weight: 600;
                  border-radius: 6px;
                  cursor: pointer;
                  transition: all 0.2s;
                }}
                button:hover {{ background: #334155; }}
                button.active {{
                  background-color: #EF4444;
                  border-color: #EF4444;
                  box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
                }}
                button.play-btn {{
                  background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
                  border: none;
                  color: #000;
                  font-weight: 800;
                }}
                button.play-btn:hover {{
                  box-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
                }}
                /* Step Sequencer Grid */
                .grid-container {{
                  display: grid;
                  grid-template-rows: repeat(3, auto);
                  gap: 8px;
                  margin-top: 10px;
                }}
                .grid-row {{
                  display: grid;
                  grid-template-columns: 80px repeat(16, 1fr);
                  align-items: center;
                  gap: 4px;
                }}
                .instrument-label {{
                  font-size: 0.75rem;
                  font-weight: bold;
                  color: #94A3B8;
                }}
                .step-cell {{
                  height: 24px;
                  background-color: #1E293B;
                  border-radius: 4px;
                  cursor: pointer;
                  transition: background-color 0.1s;
                }}
                .step-cell.active {{
                  background-color: #F43F5E;
                  box-shadow: 0 0 8px #F43F5E;
                }}
                .step-cell.highlight {{
                  border: 1.5px solid #ffffff;
                }}
                /* Export Section */
                .export-panel {{
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                }}
              </style>
            </head>
            <body>
              <div class="daw-container">
                
                <!-- Master Controls Panel -->
                <div class="panel export-panel">
                  <div style="display: flex; gap: 12px; align-items: center;">
                    <button class="play-btn" id="master-play" onclick="togglePlayback()">▶ START LOOP</button>
                    <span style="font-size: 0.85rem; color: #94A3B8;">BPM: <strong id="bpm-val">{st.session_state.project['bpm']}</strong></span>
                    <input type="range" id="tempo-slider" min="60" max="200" value="{st.session_state.project['bpm']}" step="1" oninput="updateBPM(this.value)">
                  </div>
                  <div>
                    <button onclick="syncDawToPython()" id="sync-daw-btn" style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); border: none; color: #000; font-weight: 700;">👥 SYNC TO PORTAL</button>
                    <button onclick="startRecordingMix()" id="rec-mix-btn" style="background-color: #F43F5E; border: none;">🔴 RECORD MIX</button>
                    <button onclick="stopAndExportMix()" id="export-mix-btn" disabled>💾 EXPORT WAV</button>
                    <a id="download-link" style="display: none;"></a>
                  </div>
                </div>

                <!-- Multi-Lane Real-Time Audio Mixer -->
                <div class="panel">
                  <div class="panel-title">
                    <span>TRACK CHANNELS & WAVEFORM ANALYZERS</span>
                    <span id="audio-context-status" style="font-size: 0.75rem; color: #CBD5E1;">Audio Engine: Ready (Requires play/interaction)</span>
                  </div>

                  <!-- Track 1: Melody Synth -->
                  <div class="mixer-row track-m">
                    <div>
                      <div class="track-name">Melody Synth</div>
                      <span style="font-size: 0.7rem; color: #38BDF8;">Oscillator synth</span>
                    </div>
                    <div>
                      <canvas id="canvas-melody"></canvas>
                    </div>
                    <div class="ctrl-btns">
                      <button id="mute-m" onclick="toggleMute('melody')">Mute</button>
                    </div>
                  </div>

                  <!-- Track 2: Sub-Bass -->
                  <div class="mixer-row track-b">
                    <div>
                      <div class="track-name">Sub Bass 808</div>
                      <span style="font-size: 0.7rem; color: #818CF8;">Pitch drop sweep</span>
                    </div>
                    <div>
                      <canvas id="canvas-bass"></canvas>
                    </div>
                    <div class="ctrl-btns">
                      <button id="mute-b" onclick="toggleMute('bass')">Mute</button>
                    </div>
                  </div>

                  <!-- Track 3: Drums -->
                  <div class="mixer-row track-d">
                    <div>
                      <div class="track-name">Drum Sequencer</div>
                      <span style="font-size: 0.7rem; color: #F43F5E;">Kick/Snare/Hi-hat</span>
                    </div>
                    <div>
                      <canvas id="canvas-drums"></canvas>
                    </div>
                    <div class="ctrl-btns">
                      <button id="mute-d" onclick="toggleMute('drums')">Mute</button>
                    </div>
                  </div>

                  <!-- Track 4: Microphone Voice Capture & REAL RECORDING (Requirement 3) -->
                  <div class="mixer-row track-v">
                    <div>
                      <div class="track-name">Voice & Vocals</div>
                      <span style="font-size: 0.7rem; color: #10B981;">Mic input & Rec</span>
                    </div>
                    <div>
                      <canvas id="canvas-vocals"></canvas>
                    </div>
                    <div class="ctrl-btns" style="display: flex; flex-direction: column; gap: 4px; align-items: flex-end;">
                      <div style="display: flex; gap: 4px;">
                        <button id="mic-toggle-btn" onclick="toggleMicInput()">Mic On</button>
                        <button id="vocal-rec-btn" onclick="toggleVocalRecording()" style="background-color: #38BDF8; color: #000;">🎙️ REC TAKE</button>
                        <button id="vocal-play-btn" onclick="playVocalTake(0)" disabled>▶ PLAY TAKE</button>
                      </div>
                      <label style="font-size: 0.7rem; color: #10B981; display: flex; align-items: center; gap: 4px; cursor: pointer;">
                        <input type="checkbox" id="sync-vocal-loop" style="margin:0;"> Sync with Loop Start
                      </label>
                      <label style="font-size: 0.7rem; color: #94A3B8; display: flex; align-items: center; gap: 4px; cursor: pointer;">
                        <input type="checkbox" id="mic-monitor" style="margin:0;"> Monitor mic
                      </label>
                    </div>
                  </div>
                </div>

                <!-- Step Sequencer Grid Panel -->
                <div class="panel">
                  <div class="panel-title">16-STEP BEAT ARRANGER (DRUMS & BASS)</div>
                  <div class="grid-container">
                    <div class="grid-row" id="kick-row">
                      <div class="instrument-label">🥁 KICK</div>
                    </div>
                    <div class="grid-row" id="snare-row">
                      <div class="instrument-label">👏 SNARE</div>
                    </div>
                    <div class="grid-row" id="hat-row">
                      <div class="instrument-label">⚡ HI-HAT</div>
                    </div>
                    <div class="grid-row" id="bass-row">
                      <div class="instrument-label">🎸 BASS NOTE</div>
                    </div>
                  </div>
                </div>

              </div>

              <script>
                // Web Audio Variables
                let audioCtx = null;
                let isPlaying = false;
                let bpm = {st.session_state.project['bpm']};
                let schedulerTimer = null;
                let nextNoteTime = 0.0;
                let current16thNote = 0;
                let scheduleAheadTime = 0.1; // seconds
                
                // Mute controls
                let trackMutes = {{ melody: false, bass: false, drums: false, mic: false }};

                // Audio nodes
                let masterGain = null;
                let recorderNode = null;
                let isRecordingMix = false;
                let leftChannel = [];
                let rightChannel = [];
                let recordingLength = 0;

                // Audio Analyser Nodes per channel
                let analysers = {{ melody: null, bass: null, drums: null, mic: null }};
                let canvasContexts = {{}};

                // Mic Input and unified stream handling
                let micStream = null;         // Unified raw microphone stream
                let micSourceNode = null;     // MediaStreamAudioSourceNode
                let micGainNode = null;       // Mic Gain Node
                 let micMonitorGain = null;     // Optional monitor path to speakers
                let micAnalyserNode = null;   // Reference to analysers.mic

                // Real vocal recording buffer variables (Requirement 3)
                let vocalBuffer = null;
                let isRecordingVocal = false;
                let vocalChunks = [];
                let vocalRecLength = 0;
                let vocalScriptProcessor = null;
                let vocalSourceNode = null;   // BufferSourceNode for vocal playback

                // Sequencer Grid State initialized from Python (Central state sync)
                const pythonPattern = {pattern_json};
                const gridData = pythonPattern;

                // Initialize Canvases
                const canvasIds = {{
                  melody: 'canvas-melody',
                  bass: 'canvas-bass',
                  drums: 'canvas-drums',
                  vocals: 'canvas-vocals'
                }};

                window.onload = function() {{
                  setupSequencerUI();
                  setupCanvases();
                }};

                function isValidGrid(pattern) {{
                  return pattern &&
                    ['kick','snare','hat','bass'].every(row =>
                      Array.isArray(pattern[row]) &&
                      pattern[row].length === 16 &&
                      pattern[row].every(v => v === 0 || v === 1)
                    );
                }}

                // Load and map sequencer layout from localStorage or Python state.
                function setupSequencerUI() {{
                  const savedGrid = localStorage.getItem('take_note_sequencer_grid');
                  const currentGenId = {gen_id};
                  const savedGenId = parseInt(localStorage.getItem('take_note_generation_id') || '-1');
                  
                  // If Python generated a new beat/style reference, overwrite the cache instantly!
                  if (currentGenId !== savedGenId) {{
                    Object.assign(gridData, pythonPattern);
                    localStorage.setItem('take_note_sequencer_grid', JSON.stringify(gridData));
                    localStorage.setItem('take_note_generation_id', currentGenId.toString());
                  }} else if (savedGrid) {{
                    try {{
                      const parsed = JSON.parse(savedGrid);
                      if (isValidGrid(parsed)) {{
                        Object.assign(gridData, parsed);
                      }}
                    }} catch (e) {{
                      console.error("Error loading grid from cache:", e);
                    }}
                  }}

                  const rows = ['kick', 'snare', 'hat', 'bass'];
                  rows.forEach(row => {{
                    const rowEl = document.getElementById(row + '-row');
                    while (rowEl.children.length > 1) {{
                      rowEl.removeChild(rowEl.lastChild);
                    }}
                    for (let i = 0; i < 16; i++) {{
                      const cell = document.createElement('div');
                      cell.className = 'step-cell';
                      if (gridData[row][i] === 1) cell.classList.add('active');
                      cell.dataset.step = i;
                      cell.onclick = () => {{
                        gridData[row][i] = gridData[row][i] === 1 ? 0 : 1;
                        cell.classList.toggle('active');
                        // Save changes on input to local storage
                        localStorage.setItem('take_note_sequencer_grid', JSON.stringify(gridData));
                      }};
                      rowEl.appendChild(cell);
                    }}
                  }});
                }}

                function setupCanvases() {{
                  for (let key in canvasIds) {{
                    const canvas = document.getElementById(canvasIds[key]);
                    canvasContexts[key] = canvas.getContext('2d');
                  }}
                }}

                function initAudio() {{
                  if (audioCtx) return;
                  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                  
                  // Master node configuration (Unified Master Matrix Topology)
                  // Master 
                  //  ├──→ Speakers (audioCtx.destination)
                  //  └──→ Recorder (recorderNode in startRecordingMix)
                  masterGain = audioCtx.createGain();
                  masterGain.gain.value = 0.85;

                  // Branch 1: Route Master directly to the main hardware monitors (Speakers)
                  masterGain.connect(audioCtx.destination);

                  // Setup individual analysers & gains
                  for (let key in analysers) {{
                    analysers[key] = audioCtx.createAnalyser();
                    analysers[key].fftSize = 256;
                    analysers[key].connect(masterGain);
                  }}

                  document.getElementById('audio-context-status').innerText = "Audio Engine: Active (Low-Latency)";
                  document.getElementById('audio-context-status').style.color = "#10B981";

                  // Start visual rendering loops
                  startVisualizers();
                }}

                function updateBPM(val) {{
                  bpm = parseInt(val);
                  document.getElementById('bpm-val').innerText = val;
                }}

                // ================= SYNTHESIS ENGINES =================

                // Synthesize Kick Drum (Sine Sweep)
                function playKick(time) {{
                  if (trackMutes.drums) return;
                  const osc = audioCtx.createOscillator();
                  const gain = audioCtx.createGain();
                  osc.connect(gain);
                  gain.connect(analysers.drums);

                  osc.frequency.setValueAtTime(150, time);
                  osc.frequency.exponentialRampToValueAtTime(0.01, time + 0.3);
                  
                  gain.gain.setValueAtTime(1.0, time);
                  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.3);

                  osc.start(time);
                  osc.stop(time + 0.3);
                }}

                // Synthesize Snare Drum (White Noise + Low Tone)
                function playSnare(time) {{
                  if (trackMutes.drums) return;
                  const bufferSize = audioCtx.sampleRate * 0.2;
                  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
                  const data = buffer.getChannelData(0);
                  for (let i = 0; i < bufferSize; i++) {{
                    data[i] = Math.random() * 2 - 1;
                  }}
                  
                  const noiseOsc = audioCtx.createBufferSource();
                  noiseOsc.buffer = buffer;

                  const filter = audioCtx.createBiquadFilter();
                  filter.type = 'highpass';
                  filter.frequency.setValueAtTime(1000, time);

                  const gain = audioCtx.createGain();
                  gain.gain.setValueAtTime(0.7, time);
                  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.18);

                  noiseOsc.connect(filter);
                  filter.connect(gain);
                  gain.connect(analysers.drums);

                  const oscPop = audioCtx.createOscillator();
                  const gainPop = audioCtx.createGain();
                  oscPop.frequency.setValueAtTime(180, time);
                  gainPop.gain.setValueAtTime(0.5, time);
                  gainPop.gain.exponentialRampToValueAtTime(0.001, time + 0.1);

                  oscPop.connect(gainPop);
                  gainPop.connect(analysers.drums);

                  noiseOsc.start(time);
                  oscPop.start(time);
                  noiseOsc.stop(time + 0.2);
                  oscPop.stop(time + 0.2);
                }}

                // Synthesize Crisp Hi-Hat (Filtered White Noise)
                function playHiHat(time) {{
                  if (trackMutes.drums) return;
                  const bufferSize = audioCtx.sampleRate * 0.05;
                  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
                  const data = buffer.getChannelData(0);
                  for (let i = 0; i < bufferSize; i++) {{
                    data[i] = Math.random() * 2 - 1;
                  }}

                  const noise = audioCtx.createBufferSource();
                  noise.buffer = buffer;

                  const filter = audioCtx.createBiquadFilter();
                  filter.type = 'highpass';
                  filter.frequency.setValueAtTime(8000, time);

                  const gain = audioCtx.createGain();
                  gain.gain.setValueAtTime(0.4, time);
                  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.04);

                  noise.connect(filter);
                  filter.connect(gain);
                  gain.connect(analysers.drums);

                  noise.start(time);
                  noise.stop(time + 0.05);
                }}

                // Play Bass Synthesizer Note
                function playBass(noteFreq, time) {{
                  if (trackMutes.bass) return;
                  const osc = audioCtx.createOscillator();
                  const gain = audioCtx.createGain();
                  osc.type = 'sawtooth';
                  
                  osc.connect(gain);
                  gain.connect(analysers.bass);

                  osc.frequency.setValueAtTime(noteFreq * 0.5, time); // dropped transpose
                  gain.gain.setValueAtTime(0.3, time);
                  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.25);

                  osc.start(time);
                  osc.stop(time + 0.3);
                }}

                // Lead Melody Synthesizer Notes
                function playMelodyNote(noteFreq, time) {{
                  if (trackMutes.melody) return;
                  const osc = audioCtx.createOscillator();
                  const gain = audioCtx.createGain();
                  osc.type = 'triangle';
                  
                  osc.connect(gain);
                  gain.connect(analysers.melody);

                  osc.frequency.setValueAtTime(noteFreq, time);
                  gain.gain.setValueAtTime(0.25, time);
                  gain.gain.exponentialRampToValueAtTime(0.001, time + 0.45);

                  osc.start(time);
                  osc.stop(time + 0.5);
                }}

                // ================= DRUM SCHEDULER & CLOCK =================
                function scheduler() {{
                  while (nextNoteTime < audioCtx.currentTime + scheduleAheadTime) {{
                    scheduleNote(current16thNote, nextNoteTime);
                    next16thNote();
                  }}
                  schedulerTimer = setTimeout(scheduler, 25);
                }}

                function next16thNote() {{
                  const secondsPerBeat = 60.0 / bpm;
                  const secondsPer16th = secondsPerBeat / 4;
                  nextNoteTime += secondsPer16th;
                  
                  current16thNote = (current16thNote + 1) % 16;
                }}

                function scheduleNote(step, time) {{
                  updateSequencerUIPosition(step);

                  if (gridData.kick[step] === 1) playKick(time);
                  if (gridData.snare[step] === 1) playSnare(time);
                  if (gridData.hat[step] === 1) playHiHat(time);
                  
                  if (gridData.bass[step] === 1) {{
                    const bassNotes = [130.81, 146.83, 164.81, 196.00]; // C3, D3, E3, G3 frequencies
                    const chosenNote = bassNotes[step % bassNotes.length];
                    playBass(chosenNote, time);
                    
                    if (step % 2 === 0) {{
                      playMelodyNote(chosenNote * 2, time);
                    }}
                  }}

                  // Loop Vocal Recording take exactly on loop start step 0 (Requirement 3)
                  if (step === 0) {{
                    const syncVocal = document.getElementById('sync-vocal-loop').checked;
                    if (syncVocal && vocalBuffer) {{
                      playVocalTake(time);
                    }}
                  }}
                }}

                function updateSequencerUIPosition(activeStep) {{
                  const cells = document.querySelectorAll('.step-cell');
                  cells.forEach(cell => {{
                    if (parseInt(cell.dataset.step) === activeStep) {{
                      cell.classList.add('highlight');
                    }} else {{
                      cell.classList.remove('highlight');
                    }}
                  }});
                }}

                function togglePlayback() {{
                  initAudio();
                  isPlaying = !isPlaying;
                  const playBtn = document.getElementById('master-play');
                  
                  if (isPlaying) {{
                    playBtn.innerText = "⏸ STOP LOOP";
                    playBtn.style.background = "#F43F5E";
                    nextNoteTime = audioCtx.currentTime;
                    current16thNote = 0;
                    scheduler();
                  }} else {{
                    playBtn.innerText = "▶ START LOOP";
                    playBtn.style.background = "linear-gradient(135deg, #38BDF8 0%, #818CF8 100%)";
                    clearTimeout(schedulerTimer);
                  }}
                }}

                function toggleMute(track) {{
                  trackMutes[track] = !trackMutes[track];
                  const btn = document.getElementById('mute-' + (track === 'melody' ? 'm' : (track === 'bass' ? 'b' : 'd')));
                  if (trackMutes[track]) {{
                    btn.innerText = "Unmute";
                    btn.classList.add('active');
                  }} else {{
                    btn.innerText = "Mute";
                    btn.classList.remove('active');
                  }}
                }}

                // Helper to initialize or reuse the single microphone stream
                function getOrCreateMic(callback) {{
                  initAudio();
                  if (micStream) {{
                    if (callback) callback(micStream);
                    return;
                  }}
                  
                  navigator.mediaDevices.getUserMedia({{ audio: true, video: false }})
                    .then(stream => {{
                      micStream = stream;
                      micSourceNode = audioCtx.createMediaStreamSource(stream);
                      
                      // Create micGainNode if it doesn't exist
                      if (!micGainNode) {{
                        micGainNode = audioCtx.createGain();
                        micGainNode.gain.value = 0.85; // Default volume
                      }}
                      
                      // Connect source to gain
                      micSourceNode.connect(micGainNode);
                      
                      // Feed the analyser for waveform/recording. Speaker monitoring is opt-in
                      // to reduce feedback risk when laptop speakers are in use.
                      micGainNode.connect(analysers.mic);
                      micMonitorGain = audioCtx.createGain();
                      const monitorBox = document.getElementById('mic-monitor');
                      micMonitorGain.gain.value = monitorBox && monitorBox.checked ? 0.85 : 0.0;
                      micGainNode.connect(micMonitorGain);
                      micMonitorGain.connect(masterGain);
                      if (monitorBox) {{
                        monitorBox.onchange = () => {{
                          if (micMonitorGain) micMonitorGain.gain.value = monitorBox.checked ? 0.85 : 0.0;
                        }};
                      }}
                      
                      // Update UI Button
                      const btn = document.getElementById('mic-toggle-btn');
                      if (btn) {{
                        btn.innerText = "Mic Off";
                        btn.classList.add('active');
                      }}
                      
                      if (callback) callback(stream);
                    }})
                    .catch(err => {{
                      alert("Microphone access failed: " + err);
                    }});
                }}

                function stopMic() {{
                  if (micStream) {{
                    micStream.getTracks().forEach(track => track.stop());
                    micStream = null;
                  }}
                  if (micSourceNode) {{
                    micSourceNode.disconnect();
                    micSourceNode = null;
                  }}
                  // Reset button states
                  const btn = document.getElementById('mic-toggle-btn');
                  if (btn) {{
                    btn.innerText = "Mic On";
                    btn.classList.remove('active');
                  }}
                }}

                // ================= LIVE MICROPHONE CAPTURE =================
                function toggleMicInput() {{
                  initAudio();
                  if (!micStream) {{
                    getOrCreateMic();
                  }} else {{
                    if (isRecordingVocal) {{
                      alert("Cannot turn off microphone while actively recording vocals!");
                    }} else {{
                      stopMic();
                    }}
                  }}
                }}

                // ================= REAL VOCAL RECORDER SYSTEM (Requirement 3) =================
                function toggleVocalRecording() {{
                  initAudio();
                  const recBtn = document.getElementById('vocal-rec-btn');
                  const playBtn = document.getElementById('vocal-play-btn');

                  if (!isRecordingVocal) {{
                    isRecordingVocal = true;
                    vocalChunks = [];
                    vocalRecLength = 0;
                    recBtn.innerText = "⏹ STOP";
                    recBtn.style.backgroundColor = "#EF4444";
                    playBtn.disabled = true;

                    // Use our unified getOrCreateMic helper!
                    getOrCreateMic(stream => {{
                      // Create the ScriptProcessorNode for recording
                      vocalScriptProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
                      
                      // Tap the microphone signal from micGainNode directly to the Recorder!
                      // Mic Gain ────────→ Recorder
                      micGainNode.connect(vocalScriptProcessor);
                      // Connect to a silent GainNode to trigger onaudioprocess without doubled monitoring
                      let silentVocalGain = audioCtx.createGain();
                      silentVocalGain.gain.value = 0.0;
                      vocalScriptProcessor.connect(silentVocalGain);
                      silentVocalGain.connect(audioCtx.destination);

                      vocalScriptProcessor.onaudioprocess = function(e) {{
                        if (!isRecordingVocal) return;
                        const channelData = e.inputBuffer.getChannelData(0);
                        vocalChunks.push(new Float32Array(channelData));
                        vocalRecLength += 4096;
                      }};
                    }});
                  }} else {{
                    isRecordingVocal = false;
                    recBtn.innerText = "🎙️ REC TAKE";
                    recBtn.style.backgroundColor = "#1E293B";

                    if (vocalScriptProcessor) {{
                      if (micGainNode) {{
                        try {{ micGainNode.disconnect(vocalScriptProcessor); }} catch(e) {{}}
                      }}
                      vocalScriptProcessor.disconnect();
                      vocalScriptProcessor = null;
                    }}

                    // Stop mic stream if the manual toggle is inactive
                    const micToggleBtn = document.getElementById('mic-toggle-btn');
                    const micBtnActive = micToggleBtn && micToggleBtn.classList.contains('active');
                    if (!micBtnActive) {{
                      stopMic();
                    }}

                    const flatVocal = flattenArray(vocalChunks, vocalRecLength);
                    vocalBuffer = audioCtx.createBuffer(1, flatVocal.length, audioCtx.sampleRate);
                    vocalBuffer.copyToChannel(flatVocal, 0);

                    playBtn.disabled = false;
                    alert("Vocal take recorded to memory! Check 'Sync with Loop Start' or click PLAY TAKE.");
                  }}
                }}

                function playVocalTake(time) {{
                  if (!vocalBuffer) return;
                  initAudio();

                  if (vocalSourceNode) {{
                    try {{ vocalSourceNode.stop(); }} catch(e) {{}}
                  }}

                  vocalSourceNode = audioCtx.createBufferSource();
                  vocalSourceNode.buffer = vocalBuffer;
                  vocalSourceNode.connect(analysers.mic);
                  
                  if (time === 0) {{
                    vocalSourceNode.start(audioCtx.currentTime);
                  }} else {{
                    vocalSourceNode.start(time);
                  }}
                }}

                // ================= REAL WAVEFORM GRAPHICAL RENDERING =================
                function startVisualizers() {{
                  const renderBuffer = new Uint8Array(128);
                  const channelKeys = {{
                    melody: 'melody',
                    bass: 'bass',
                    drums: 'drums',
                    vocals: 'mic'
                  }};

                  function drawFrame() {{
                    requestAnimationFrame(drawFrame);
                    
                    for (let key in channelKeys) {{
                      const analyserKey = channelKeys[key];
                      const ctx = canvasContexts[key];
                      const canvas = document.getElementById(canvasIds[key]);
                      if (!ctx || !canvas) continue;

                      const width = canvas.width;
                      const height = canvas.height;

                      ctx.clearRect(0, 0, width, height);

                      const analyser = analysers[analyserKey];
                      if (analyser && isPlaying && !trackMutes[analyserKey]) {{
                        analyser.getByteTimeDomainData(renderBuffer);
                        ctx.strokeStyle = getChannelStroke(key);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        
                        const sliceWidth = width * 1.0 / renderBuffer.length;
                        let x = 0;
                        for (let i = 0; i < renderBuffer.length; i++) {{
                          const v = renderBuffer[i] / 128.0;
                          const y = v * height / 2;
                          if (i === 0) {{
                            ctx.moveTo(x, y);
                          }} else {{
                            ctx.lineTo(x, y);
                          }}
                          x += sliceWidth;
                        }}
                        ctx.lineTo(width, height / 2);
                        ctx.stroke();
                      }} else {{
                        ctx.strokeStyle = '#27272A';
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(0, height / 2);
                        ctx.lineTo(width, height / 2);
                        ctx.stroke();
                      }}
                    }}
                  }}
                  drawFrame();
                }}

                function getChannelStroke(key) {{
                  if (key === 'melody') return '#38BDF8';
                  if (key === 'bass') return '#818CF8';
                  if (key === 'drums') return '#F43F5E';
                  return '#10B981';
                }}

                // ================= STREAMLIT STATE SYNCHRONIZER (Requirement 13) =================
                function syncDawToPython() {{
                  if (!isValidGrid(gridData)) {{
                    alert("The sequencer grid is invalid and cannot be synchronized.");
                    return;
                  }}
                  const parentUrl = new URL(window.parent.location.href);
                  parentUrl.searchParams.set("sync_bpm", Math.max(60, Math.min(200, Math.round(bpm))));
                  parentUrl.searchParams.set("sync_pattern", JSON.stringify(gridData));
                  window.parent.location.href = parentUrl.href;
                }}

                // ================= EXPORT SYSTEM: MASTER 16-BIT PCM WAV RECORDER (Requirement 2) =================
                function startRecordingMix() {{
                  initAudio();
                  leftChannel = [];
                  rightChannel = [];
                  recordingLength = 0;
                  isRecordingMix = true;

                  // Create real-time ScriptProcessor capture node (Branch 2 of Master)
                  // Master 
                  //  └──→ Recorder
                  recorderNode = audioCtx.createScriptProcessor(4096, 2, 2);
                  masterGain.connect(recorderNode);
                  // Connect to a silent GainNode to trigger onaudioprocess without doubled monitoring
                  let silentMixGain = audioCtx.createGain();
                  silentMixGain.gain.value = 0.0;
                  recorderNode.connect(silentMixGain);
                  silentMixGain.connect(audioCtx.destination);

                  recorderNode.onaudioprocess = function(e) {{
                    if (!isRecordingMix) return;
                    const left = e.inputBuffer.getChannelData(0);
                    const right = e.inputBuffer.numberOfChannels > 1
                      ? e.inputBuffer.getChannelData(1)
                      : left;
                    
                    // Clone because buffers are recycled
                    leftChannel.push(new Float32Array(left));
                    rightChannel.push(new Float32Array(right));
                    recordingLength += 4096;
                  }};

                  document.getElementById('rec-mix-btn').innerText = "⏹ STOP RECORDING";
                  document.getElementById('rec-mix-btn').style.backgroundColor = "#EF4444";
                  document.getElementById('export-mix-btn').disabled = true;
                }}

                function stopAndExportMix() {{
                  if (isRecordingMix) {{
                    isRecordingMix = false;
                    
                    if (recorderNode) {{
                      recorderNode.disconnect();
                      masterGain.disconnect(recorderNode);
                    }}

                    document.getElementById('rec-mix-btn').innerText = "🔴 RECORD MIX";
                    document.getElementById('rec-mix-btn').style.backgroundColor = "#F43F5E";

                    // Flatten Buffers
                    const leftBuffer = flattenArray(leftChannel, recordingLength);
                    const rightBuffer = flattenArray(rightChannel, recordingLength);

                    // Interleave
                    const interleaved = interleave(leftBuffer, rightBuffer);

                    // Compile 16-Bit PCM WAV ArrayBuffer Structure
                    const buffer = new ArrayBuffer(44 + interleaved.length * 2);
                    const view = new DataView(buffer);

                    writeString(view, 0, 'RIFF');
                    view.setUint32(4, 36 + interleaved.length * 2, true);
                    writeString(view, 8, 'WAVE');
                    writeString(view, 12, 'fmt ');
                    view.setUint32(16, 16, true);
                    view.setUint16(20, 1, true); // PCM Format
                    view.setUint16(22, 2, true); // Stereo Channels
                    view.setUint32(24, audioCtx.sampleRate, true);
                    view.setUint32(28, audioCtx.sampleRate * 4, true); // byte rate
                    view.setUint16(32, 4, true); // block align
                    view.setUint16(34, 16, true); // bit depth
                    writeString(view, 36, 'data');
                    view.setUint32(40, interleaved.length * 2, true);

                    // Write audio samples
                    let offset = 44;
                    for (let i = 0; i < interleaved.length; i++, offset += 2) {{
                      let s = Math.max(-1, Math.min(1, interleaved[i]));
                      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                    }}

                    const blob = new Blob([view], {{ type: 'audio/wav' }});
                    const audioUrl = URL.createObjectURL(blob);

                    const dlBtn = document.getElementById('export-mix-btn');
                    dlBtn.disabled = false;

                    const link = document.getElementById('download-link');
                    link.href = audioUrl;
                    link.download = `take_note_beat_${{Date.now()}}.wav`;
                    
                    alert("Stereo compilation completed! Download your real 16-bit uncompressed WAV file using EXPORT WAV.");
                  }} else {{
                    const link = document.getElementById('download-link');
                    link.click();
                  }}
                }}

                function flattenArray(channelBuffer, length) {{
                  const result = new Float32Array(length);
                  let offset = 0;
                  for (let i = 0; i < channelBuffer.length; i++) {{
                    const buffer = channelBuffer[i];
                    result.set(buffer, offset);
                    offset += buffer.length;
                  }}
                  return result;
                }}

                function interleave(leftChannel, rightChannel) {{
                  const length = leftChannel.length + rightChannel.length;
                  const result = new Float32Array(length);
                  let inputIndex = 0;
                  for (let index = 0; index < length; index += 2) {{
                    result[index] = leftChannel[inputIndex];
                    result[index + 1] = rightChannel[inputIndex];
                    inputIndex++;
                  }}
                  return result;
                }}

                function writeString(view, offset, string) {{
                  for (let i = 0; i < string.length; i++) {{
                    view.setUint8(offset + i, string.charCodeAt(i));
                  }}
                }}
              </script>
            </body>
            </html>
            """
            
            # Embed real-time Web Audio API inside Streamlit Component
            st.caption("After editing the DAW grid or tempo, click **SYNC TO PORTAL** before saving so Streamlit receives the latest DAW state.")
            st.components.v1.html(daw_html, height=750, scrolling=True)

        # ==========================================
        # TAB 2: LYRIC MUSIC ACADEMY
        # ==========================================
        with tab_academy:
            st.markdown("## 🎓 LYRIC ACADEMY INTERACTIVE CLASSROOM")
            st.write("Welcome back to your music tutoring system. Complete scale exercises and match tempos directly on your screen to log learning milestones.")
            
            col_ac1, col_ac2 = st.columns(2)
            with col_ac1:
                st.markdown("### 🎹 Chords & Scales Challenge")
                st.write("Since we are working with standard minor scales, select the correct root minor chord relative to C Major:")
                chord_guess = st.selectbox("Your Answer Choice:", ["D Minor", "A Minor", "E Minor", "G Minor"])
                
                if st.button("Verify Answer", key="theory_btn"):
                  if chord_guess == "A Minor":
                    st.success("🎉 Correct! A Minor is the natural relative minor chord of C Major (sharing the exact same key signature).")
                    if "Theory: Relative Minors" not in st.session_state.lessons_completed:
                      st.session_state.lessons_completed.append("Theory: Relative Minors")
                      st.rerun()
                  else:
                    st.error("Not quite! Remember that relative minors share the same set of natural notes. Let's try again.")
            
            with col_ac2:
                st.markdown("### ⏱️ High-Precision Rhythm Trainer")
                st.write("Match tempo timings precisely. Press **SPACEBAR** or tap the screen exactly on the pulsing visual glow.")
                
                # Embedded Web Audio High-Precision Metronome Game (Real timing engine)
                rhythm_game_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                  <style>
                    body {{
                      background-color: #0A0D14;
                      color: #E2E8F0;
                      font-family: -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                      margin: 0;
                      padding: 10px;
                      text-align: center;
                    }}
                    .metronome-visual {{
                      width: 90px;
                      height: 90px;
                      border-radius: 50%;
                      background-color: #111622;
                      border: 4px solid #F43F5E;
                      margin: 12px auto;
                      display: flex;
                      justify-content: center;
                      align-items: center;
                      transition: transform 0.08s ease;
                      box-shadow: 0 0 10px rgba(244, 63, 94, 0.2);
                    }}
                    .metronome-visual.flash {{
                      transform: scale(1.18);
                      background-color: #F43F5E;
                      box-shadow: 0 0 35px #F43F5E, inset 0 0 15px rgba(255,255,255,0.6);
                    }}
                    .metronome-visual span {{
                      font-weight: 800;
                      color: #ffffff;
                      font-size: 1.1rem;
                      letter-spacing: 0.05rem;
                    }}
                    .btn-tap {{
                      background: linear-gradient(135deg, #EC4899 0%, #F43F5E 100%);
                      color: #ffffff;
                      font-weight: 800;
                      padding: 10px 20px;
                      border: none;
                      border-radius: 8px;
                      font-size: 0.95rem;
                      cursor: pointer;
                      letter-spacing: 0.05rem;
                      box-shadow: 0 0 15px rgba(244, 63, 94, 0.4);
                      transition: all 0.2s;
                      width: 100%;
                      margin-bottom: 8px;
                    }}
                    .btn-tap:hover {{
                      box-shadow: 0 0 25px rgba(244, 63, 94, 0.7);
                      transform: translateY(-1px);
                    }}
                    .btn-tap:active {{
                      transform: scale(0.98);
                    }}
                    .readout {{
                      font-size: 1.1rem;
                      font-weight: bold;
                      margin: 8px 0;
                      height: 25px;
                    }}
                    .score-badge {{
                      display: inline-block;
                      padding: 4px 12px;
                      border-radius: 12px;
                      font-size: 0.85rem;
                      font-weight: 700;
                      margin-top: 5px;
                    }}
                    .rating-perfect {{ color: #10B981; }}
                    .rating-good {{ color: #818CF8; }}
                    .rating-miss {{ color: #F43F5E; }}
                    
                    .btn-log {{
                      background-color: #1E293B;
                      border: 1px solid #334155;
                      color: #ffffff;
                      padding: 8px 16px;
                      font-size: 0.8rem;
                      font-weight: 600;
                      border-radius: 6px;
                      cursor: pointer;
                      transition: all 0.2s;
                      width: 100%;
                    }}
                    .btn-log:hover {{
                      background-color: #334155;
                    }}
                  </style>
                </head>
                <body>
                  <div>
                    <button class="btn-tap" id="toggle-met-btn" onclick="toggleLocalMetronome()">▶ START METRONOME</button>
                    <div class="metronome-visual" id="orb-visual">
                      <span id="bpm-label">{bpm}</span>
                    </div>
                    <button class="btn-tap" style="background: #111622; border: 1px solid #334155;" id="tap-btn" onmousedown="handleTap()">🎯 TAP TEMPO (or SPACE)</button>
                    
                    <div class="readout" id="timing-readout">Press start to begin...</div>
                    <div id="score-container" style="display:none; margin-bottom: 12px;">
                      <div class="score-badge" id="rating-badge"></div>
                    </div>
                    <button class="btn-log" id="log-score-btn" style="display:none;" onclick="logScoreToPython()">💾 LOG SCORE TO LEDGER</button>
                  </div>

                  <script>
                    let audioCtx = null;
                    let metronomeInterval = null;
                    let bpm = {bpm};
                    let lastBeatTime = 0;
                    let nextBeatTime = 0;
                    let lastScore = 0;

                    function initAudio() {{
                      if (audioCtx) return;
                      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    }}

                    function playClick(time) {{
                      const osc = audioCtx.createOscillator();
                      const gain = audioCtx.createGain();
                      osc.connect(gain);
                      gain.connect(audioCtx.destination);

                      osc.frequency.setValueAtTime(880, time); // 880Hz high click
                      gain.gain.setValueAtTime(0.3, time);
                      gain.gain.exponentialRampToValueAtTime(0.001, time + 0.05);

                      osc.start(time);
                      osc.stop(time + 0.06);
                    }}

                    function toggleLocalMetronome() {{
                      initAudio();
                      const btn = document.getElementById('toggle-met-btn');
                      const orb = document.getElementById('orb-visual');

                      if (!metronomeInterval) {{
                        // Start Metronome
                        btn.innerText = "⏸ STOP METRONOME";
                        btn.style.background = "#EF4444";
                        
                        const intervalSeconds = 60.0 / bpm;
                        nextBeatTime = audioCtx.currentTime;
                        
                        metronomeInterval = setInterval(() => {{
                          const currentTime = audioCtx.currentTime;
                          if (currentTime >= nextBeatTime - 0.02) {{
                            playClick(nextBeatTime);
                            lastBeatTime = nextBeatTime;
                            
                            // Visual flash
                            orb.classList.add('flash');
                            setTimeout(() => orb.classList.remove('flash'), 80);
                            
                            nextBeatTime += intervalSeconds;
                          }}
                        }}, 15);
                        document.getElementById('timing-readout').innerText = "Metronome active! Tap in sync.";
                      }} else {{
                        // Stop Metronome
                        clearInterval(metronomeInterval);
                        metronomeInterval = null;
                        btn.innerText = "▶ START METRONOME";
                        btn.style.background = "linear-gradient(135deg, #EC4899 0%, #F43F5E 100%)";
                        document.getElementById('timing-readout').innerText = "Metronome stopped.";
                      }}
                    }}

                    function handleTap() {{
                      if (!metronomeInterval) {{
                        initAudio();
                        toggleLocalMetronome();
                        return;
                      }}

                      const tapTime = audioCtx.currentTime;
                      const intervalSeconds = 60.0 / bpm;
                      
                      // Calculate offsets
                      const timeSinceLast = tapTime - lastBeatTime;
                      const timeToNext = nextBeatTime - tapTime;
                      
                      let deltaSeconds = 0;
                      if (timeSinceLast < timeToNext) {{
                        deltaSeconds = timeSinceLast; // Late
                      }} else {{
                        deltaSeconds = -timeToNext; // Early
                      }}

                      const deltaMs = Math.round(deltaSeconds * 1000);
                      const absDelta = Math.abs(deltaMs);

                      // Precise grading math curves
                      let score = 0;
                      let rating = "";
                      let rClass = "";

                      if (absDelta <= 15) {{
                        score = Math.round(100 - absDelta * 0.2);
                        rating = "Perfect! 🎯";
                        rClass = "rating-perfect";
                      }} else if (absDelta <= 100) {{
                        score = Math.round(97 - (absDelta - 15) * 0.317);
                        rating = "Good timing! 👍";
                        rClass = "rating-good";
                      }} else if (absDelta <= 250) {{
                        score = Math.round(70 - (absDelta - 100) * 0.333);
                        rating = "Slightly off-beat! ⚠️";
                        rClass = "rating-good";
                      }} else {{
                        score = Math.max(0, Math.round(20 - (absDelta - 250) * 0.2));
                        rating = "Miss! ❌";
                        rClass = "rating-miss";
                      }}

                      lastScore = score;

                      // Display exact delta and timing direction
                      const dirText = deltaMs >= 0 ? "late" : "early";
                      document.getElementById('timing-readout').innerHTML = `<strong>${absDelta} ms ${dirText}</strong>`;
                      
                      const scoreBadge = document.getElementById('rating-badge');
                      scoreBadge.className = `score-badge ${rClass}`;
                      scoreBadge.innerText = `${rating} Score: ${score}% accuracy`;
                      
                      document.getElementById('score-container').style.display = 'block';
                      document.getElementById('log-score-btn').style.display = 'block';
                    }}

                    function logScoreToPython() {{
                      const parentUrl = new URL(window.parent.location.href);
                      parentUrl.searchParams.set("rhythm_score", lastScore);
                      window.parent.location.href = parentUrl.href;
                    }}

                    // Bind spacebar trigger
                    window.addEventListener('keydown', (e) => {{
                      if (e.code === 'Space') {{
                        e.preventDefault(); // Stop page scrolling
                        handleTap();
                        
                        // Visual click feedback on the tap button
                        const tapBtn = document.getElementById('tap-btn');
                        if (tapBtn) {{
                          tapBtn.style.background = '#1E293B';
                          setTimeout(() => tapBtn.style.background = '#111622', 80);
                        }}
                      }}
                    }});
                  </script>
                </body>
                </html>
                """
                
                # Render the high-precision metronome
                st.components.v1.html(rhythm_game_html, height=330, scrolling=False)

        # ==========================================
        # TAB 3: PROGRESS TRACKING & ACCOUNT
        # ==========================================
        with tab_progress:
            st.markdown("## 📈 YOUR ACADEMY PROGRESS LOG")
            
            if not st.session_state.logged_in:
                st.markdown("### 🔒 Create Your Take Note Local Profile")
                st.write("This demo profile uses an email-format check to unlock the local progress ledger. It is not a secure account or authentication system.")
                
                email_input = st.text_input("Enter your Email Address:", placeholder="artist@producer.com")
                if st.button("Register & Unlock Complete Studio Mode"):
                  if email_input and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email_input.strip()):
                    st.session_state.logged_in = True
                    st.session_state.email = email_input
                    st.success(f"Local profile unlocked for {email_input.strip()}! Progress ledger is active for this session.")
                    st.rerun()
                  else:
                    st.error("Please enter a valid email address.")
            else:
                st.markdown(f"### Connected Profile: `{st.session_state.email}`")
                
                c_st1, c_st2, c_st3 = st.columns(3)
                with c_st1:
                    st.metric("Lessons Completed", len(st.session_state.lessons_completed))
                with c_st2:
                    avg_score = sum(st.session_state.rhythm_scores) // len(st.session_state.rhythm_scores) if st.session_state.rhythm_scores else 0
                    st.metric("Avg Rhythm Match Accuracy", f"{avg_score}%")
                with c_st3:
                    st.metric("Saved Projects Active", len(st.session_state.saved_projects))

                st.markdown("### Completed Milestones")
                for lesson in st.session_state.lessons_completed:
                  st.write(f"✓ `{lesson}` — Completed & Logged")

                if st.button("Log Out of Profile"):
                  st.session_state.logged_in = False
                  st.session_state.email = ""
                  st.rerun()

    # ------------------------------------------
    # RIGHT SIDEBAR: COLLAPSIBLE COACH (LYRIC)
    # ------------------------------------------
    with right_col:
        st.markdown('<div class="sidebar-header">🤖 LYRIC MUSIC COACH</div>', unsafe_allow_html=True)
        st.write("Lyric is actively observing your project layout. Ask mixing, theory, or arrangement questions below.")
        
        # Mini glowing orb inside workspace to show Lyric's presence
        orb_sm_col1, orb_sm_col2 = st.columns([1, 4])
        with orb_sm_col1:
            st.markdown("""
                <div style="width: 35px; height: 35px; border-radius: 50%; background: radial-gradient(circle, #38BDF8 0%, rgba(56, 189, 248, 0.2) 80%); box-shadow: 0 0 10px #38BDF8; margin-top:5px;"></div>
            """, unsafe_allow_html=True)
        with orb_sm_col2:
            st.markdown("<p style='font-size:0.85rem; color:#94A3B8; margin:0;'>Active Mode: Real Audio Analyser Sweep & Sound Guidance</p>", unsafe_allow_html=True)

        st.markdown("--- ")

        # Live chat assistant interface
        st.markdown("#### Lyric Coaching Log & Feedback")
        for chat in st.session_state.chat_history:
            if chat["role"] == "assistant":
                st.markdown(f"🤖 **Lyric:** {chat['content']}")
            else:
                st.markdown(f"👤 **You:** {chat['content']}")
        
        user_msg = st.text_input("Ask Lyric a music question:", key="chat_input_v3")
        if st.button("Send", key="chat_send_btn_v3"):
            if user_msg:
                st.session_state.chat_history.append({"role": "user", "content": user_msg})
                
                # Simple responsive coaching rules
                resp = "I recommend exploring minor scales if you're writing a melancholy chord progression."
                if "beat" in user_msg.lower() or "generate" in user_msg.lower() or "loop" in user_msg.lower():
                    resp = "Our active tempo loop is great for building transient drum patterns. Try adjusting individual grid toggles to shape unique syncopations!"
                elif "chord" in user_msg.lower() or "theory" in user_msg.lower() or "relative" in user_msg.lower():
                    resp = "Look for relative chords inside the Academy. Sharing keys lets you construct seamless, highly emotional bridge changes."
                elif "sing" in user_msg.lower() or "vocal" in user_msg.lower() or "mic" in user_msg.lower():
                    resp = "Your vocal monitoring stream registers pitch values directly. Practice smooth humming scale glides to keep notes steady!"
                
                st.session_state.chat_history.append({"role": "assistant", "content": resp})
                st.rerun()

        st.markdown("--- ")
        
        # Interactive Lyrics Pad
        st.markdown("#### ✍️ Interactive Song Lyrics Notepad")
        lyrics_area = st.text_area(
            "Write your thoughts or edit generated lyrics:", 
            value=st.session_state.lyrics, 
            height=250, 
            key="lyrics_notepad_v3"
        )
        if lyrics_area != st.session_state.lyrics:
            st.session_state.lyrics = lyrics_area
