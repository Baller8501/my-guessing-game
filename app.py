
import streamlit as st
from supabase import create_client, Client
import random
from datetime import datetime, timezone

# ==========================================
# PAGE SETTINGS
# ==========================================

st.set_page_config(
    page_title="Guess the Number Champion",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Guess the Number Champion")
st.write("Guess the number. Earn coins. Become champion!")

# ==========================================
# SUPABASE CONNECTION
# ==========================================

@st.cache_resource
def connect_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


try:
    supabase: Client = connect_supabase()
except Exception as e:
    st.error("Could not connect to Supabase.")
    st.exception(e)
    st.stop()


# ==========================================
# SESSION STATE
# ==========================================

defaults = {
    "user": None,
    "username": None,
    "target": None,
    "attempts": 0,
    "coins": 0,
    "score": 0,
    "level": 1,
    "games_won": 0,
    "levels_completed": 0,
    "message": "",
    "game_over": False,
    "hint_used": False,
    "needs_profile_setup": False,
    "challenge_date": None,
    "challenge_progress": {}
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

def load_profile(user_id):
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def create_profile(user_id, username):
    return supabase.table("profiles").insert({
        "id": user_id,
        "username": username
    }).execute()


def load_stats(user_id):
    result = (
        supabase.table("game_stats")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    if result.data:
        return result.data[0]

    return {
        "coins": 0,
        "score": 0,
        "games_won": 0,
        "levels_completed": 0
    }


def save_stats():
    data = {
        "user_id": st.session_state.user.id,
        "coins": st.session_state.coins,
        "score": st.session_state.score,
        "games_won": st.session_state.games_won,
        "levels_completed": st.session_state.levels_completed
    }

    supabase.table("game_stats").upsert(
        data,
        on_conflict="user_id"
    ).execute()


# ==========================================
# DAILY CHALLENGES
# ==========================================

CHALLENGES = {
    "level_master": {
        "name": "🏅 Level Master",
        "description": "Complete 2 levels",
        "goal": 2,
        "reward": 20
    },
    "coin_collector": {
        "name": "🪙 Coin Collector",
        "description": "Earn 25 coins from completed levels",
        "goal": 25,
        "reward": 25
    },
    "guessing_expert": {
        "name": "🎯 Guessing Expert",
        "description": "Submit 5 guesses",
        "goal": 5,
        "reward": 15
    }
}


def today_utc():
    return datetime.now(timezone.utc).date().isoformat()


def load_daily_challenges():
    today = today_utc()

    if st.session_state.challenge_date == today:
        return

    user_id = st.session_state.user.id

    result = (
        supabase.table("daily_challenge_progress")
        .select("*")
        .eq("user_id", user_id)
        .eq("challenge_date", today)
        .execute()
    )

    progress = {}

    for challenge_id, challenge in CHALLENGES.items():
        progress[challenge_id] = {
            "progress": 0,
            "completed": False,
            "reward_claimed": False
        }

    for row in result.data:
        challenge_id = row["challenge_id"]

        if challenge_id in progress:
            progress[challenge_id] = {
                "progress": row["progress"],
                "completed": row["completed"],
                "reward_claimed": row["reward_claimed"]
            }

    st.session_state.challenge_date = today
    st.session_state.challenge_progress = progress


def update_challenge(challenge_id, amount):
    today = today_utc()

    if st.session_state.challenge_date != today:
        load_daily_challenges()

    challenge = CHALLENGES[challenge_id]
    current = st.session_state.challenge_progress[challenge_id]

    if current["reward_claimed"]:
        return

    new_progress = min(
        current["progress"] + amount,
        challenge["goal"]
    )

    completed = new_progress >= challenge["goal"]
    reward_claimed = current["reward_claimed"]

    st.session_state.challenge_progress[challenge_id] = {
        "progress": new_progress,
        "completed": completed,
        "reward_claimed": reward_claimed
    }

    if completed and not reward_claimed:
        st.session_state.coins += challenge["reward"]
        st.session_state.challenge_progress[challenge_id][
            "reward_claimed"
        ] = True

        st.success(
            f"🎉 Daily challenge completed! "
            f"You earned {challenge['reward']} bonus coins!"
        )

    supabase.table("daily_challenge_progress").upsert(
        {
            "user_id": st.session_state.user.id,
            "challenge_date": today,
            "challenge_id": challenge_id,
            "progress": new_progress,
            "completed": completed,
            "reward_claimed": st.session_state.challenge_progress[
                challenge_id
            ]["reward_claimed"]
        },
        on_conflict="user_id,challenge_date,challenge_id"
    ).execute()


def display_daily_challenges():
    st.divider()
    st.header("🎯 Daily Challenges")
    st.caption("Your daily challenges reset at midnight UTC.")

    for challenge_id, challenge in CHALLENGES.items():
        progress = st.session_state.challenge_progress[challenge_id]

        st.subheader(challenge["name"])
        st.write(challenge["description"])

        st.progress(
            min(progress["progress"] / challenge["goal"], 1.0)
        )

        st.write(
            f"Progress: {progress['progress']}/{challenge['goal']} "
            f"• Reward: {challenge['reward']} coins"
        )

        if progress["reward_claimed"]:
            st.success("Challenge completed! Reward collected.")
        elif progress["completed"]:
            st.success("Challenge completed!")


# ==========================================
# GAME FUNCTIONS
# ==========================================

LEVELS = [
    (1, 10),
    (11, 30),
    (31, 50),
    (51, 70),
    (71, 90),
    (91, 110),
    (111, 130),
    (131, 150),
    (151, 170),
    (171, 190)
]


def start_level():
    low, high = LEVELS[st.session_state.level - 1]

    st.session_state.target = random.randint(low, high)
    st.session_state.attempts = 0
    st.session_state.game_over = False
    st.session_state.hint_used = False
    st.session_state.message = ""


# FIXED: Score is no longer reset when starting a new cycle.
def reset_game():
    st.session_state.level = 1
    st.session_state.game_over = False
    st.session_state.target = None
    start_level()


# ==========================================
# LOGIN AND REGISTRATION
# ==========================================

if st.session_state.user is None:

    login_tab, signup_tab = st.tabs(
        ["🔐 Login", "📝 Create Account"]
    )

    with login_tab:
        st.subheader("Welcome back!")

        email = st.text_input(
            "Email address",
            key="login_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login", use_container_width=True):

            if not email or not password:
                st.warning("Enter your email and password.")

            else:
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })

                    st.session_state.user = response.user

                    profile = load_profile(response.user.id)

                    if not profile:
                        st.session_state.needs_profile_setup = True
                        st.rerun()

                    st.session_state.username = profile["username"]

                    stats = load_stats(response.user.id)

                    for field in [
                        "coins",
                        "score",
                        "games_won",
                        "levels_completed"
                    ]:
                        st.session_state[field] = stats[field]

                    load_daily_challenges()
                    start_level()
                    st.rerun()

                except Exception as e:
                    st.error("Login failed.")
                    st.exception(e)

    with signup_tab:
        st.subheader("Create your champion account!")

        username = st.text_input(
            "Choose a username",
            key="signup_username"
        )

        email = st.text_input(
            "Email address",
            key="signup_email"
        )

        password = st.text_input(
            "Choose a password (at least 8 characters)",
            type="password",
            key="signup_password"
        )

        if st.button("Create Account", use_container_width=True):

            if not username or not email or not password:
                st.warning("Please complete all fields.")

            elif len(username.strip()) < 3:
                st.warning("Username must have at least 3 characters.")

            elif len(password) < 8:
                st.warning("Password must have at least 8 characters.")

            else:
                try:
                    response = supabase.auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {
                            "data": {
                                "username": username.strip()
                            }
                        }
                    })

                    if response.user is None:
                        st.error("Account creation failed.")
                        st.stop()

                    if response.session is None:
                        st.success(
                            "Account created! Check your email "
                            "if email confirmation is enabled, "
                            "then log in."
                        )
                        st.stop()

                    create_profile(
                        response.user.id,
                        username.strip()
                    )

                    supabase.table("game_stats").upsert({
                        "user_id": response.user.id,
                        "coins": 0,
                        "score": 0,
                        "games_won": 0,
                        "levels_completed": 0
                    }, on_conflict="user_id").execute()

                    st.success("Account created! Please log in.")

                except Exception as e:
                    st.error("Registration failed.")
                    st.exception(e)

    st.stop()


# ==========================================
# PROFILE RECOVERY
# ==========================================

if (
    st.session_state.user is not None
    and st.session_state.needs_profile_setup
):
    st.header("🎮 Finish setting up your player profile")

    st.write(
        "Your email account is confirmed, but your game profile "
        "was not created during your original sign-up."
    )

    user_metadata = (
        getattr(st.session_state.user, "user_metadata", {}) or {}
    )

    suggested_username = user_metadata.get("username", "")

    recovery_username = st.text_input(
        "Your game username",
        value=suggested_username,
        key="recovery_username"
    )

    if st.button("Create My Player Profile"):

        clean_username = recovery_username.strip()

        if len(clean_username) < 3 or len(clean_username) > 20:
            st.warning("Your username must be between 3 and 20 characters.")

        elif not clean_username.replace("_", "").isalnum():
            st.warning("Use only letters, numbers, and underscores.")

        else:
            try:
                existing = (
                    supabase.table("profiles")
                    .select("id")
                    .ilike("username", clean_username)
                    .execute()
                )

                if existing.data:
                    st.error("That username is already in use.")

                else:
                    create_profile(
                        st.session_state.user.id,
                        clean_username
                    )

                    supabase.table("game_stats").upsert({
                        "user_id": st.session_state.user.id,
                        "coins": 0,
                        "score": 0,
                        "games_won": 0,
                        "levels_completed": 0
                    }, on_conflict="user_id").execute()

                    st.session_state.username = clean_username
                    st.session_state.needs_profile_setup = False

                    stats = load_stats(st.session_state.user.id)

                    for field in [
                        "coins",
                        "score",
                        "games_won",
                        "levels_completed"
                    ]:
                        st.session_state[field] = stats[field]

                    load_daily_challenges()
                    start_level()

                    st.success("Your player profile is ready!")
                    st.rerun()

            except Exception as e:
                st.error("We couldn't create your player profile.")
                st.exception(e)

    st.stop()


# ==========================================
# PLAYER PROFILE SIDEBAR
# ==========================================

st.sidebar.title("👤 Player Profile")
st.sidebar.write(
    f"Welcome, **{st.session_state.username}!**"
)

if st.sidebar.button("Logout"):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    for key in defaults:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


st.sidebar.metric("🪙 Coins", st.session_state.coins)
st.sidebar.metric("⭐ Score", st.session_state.score)
st.sidebar.metric("🏆 Games Won", st.session_state.games_won)
st.sidebar.metric(
    "🎯 Levels Completed",
    st.session_state.levels_completed
)


# ==========================================
# LOAD AND DISPLAY DAILY CHALLENGES
# ==========================================

load_daily_challenges()
display_daily_challenges()


# ==========================================
# MAIN GAME + LEADERBOARD
# ==========================================

left_col, right_col = st.columns([3, 1])


# ==========================================
# LEFT SIDE: MAIN GAME
# ==========================================

with left_col:

    st.divider()
    st.header(f"🎮 Level {st.session_state.level}")

    low, high = LEVELS[st.session_state.level - 1]

    st.write(
        f"I'm thinking of a number between **{low} and {high}**."
    )

    if st.session_state.target is None:
        start_level()

    if st.session_state.game_over:

        st.warning("This level is finished!")

        if st.button("Play Again"):
            reset_game()
            st.rerun()

    else:

        guess = st.number_input(
            "Enter your guess",
            min_value=low,
            max_value=high,
            step=1,
            key="guess_input"
        )

        if st.button("Submit Guess", use_container_width=True):

            st.session_state.attempts += 1

            update_challenge("guessing_expert", 1)

            if guess == st.session_state.target:

                reward = 10 + max(
                    0,
                    5 - st.session_state.attempts
                )

                st.session_state.coins += reward
                st.session_state.score += reward
                st.session_state.games_won += 1
                st.session_state.levels_completed += 1

                update_challenge("level_master", 1)
                update_challenge("coin_collector", reward)

                st.success(
                    f"🎉 Correct! You earned {reward} coins!"
                )

                if st.session_state.level == 10:

                    st.balloons()
                    st.success("🏆 YOU ARE THE ULTIMATE CHAMPION!")

                    save_stats()
                    st.session_state.game_over = True

                else:

                    st.session_state.level += 1
                    save_stats()
                    start_level()

            elif guess < st.session_state.target:

                st.session_state.message = (
                    "📈 Too low! Try a higher number."
                )

            else:

                st.session_state.message = (
                    "📉 Too high! Try a lower number."
                )

            save_stats()
            st.rerun()

        if st.session_state.message:
            st.info(st.session_state.message)


# ==========================================
# RIGHT SIDE: GLOBAL LEADERBOARD
# ==========================================

with right_col:

    st.divider()
    st.header("🏆 Global Leaderboard")

    try:
        leaderboard = supabase.rpc(
            "get_leaderboard"
        ).execute()

        if leaderboard.data:

            for position, player in enumerate(
                leaderboard.data,
                start=1
            ):

                st.write(
                    f"**{position}. {player['username']}**"
                )

                st.caption(
                    f"⭐ {player['score']} points "
                    f"• 🎯 {player['levels_completed']} levels"
                )

                st.divider()

        else:
            st.info("No leaderboard entries yet.")

    except Exception:
        st.warning("Leaderboard could not be loaded.")


# ==========================================
# POWER-UP SHOP
# ==========================================

st.divider()
st.header("🛒 Power-Up Shop")

st.write(f"Your coins: 🪙 {st.session_state.coins}")

if st.button("💡 Buy a Hint (20 coins)"):

    if st.session_state.coins >= 20:

        if st.session_state.target is None:
            start_level()

        st.session_state.coins -= 20
        st.session_state.hint_used = True

        target = st.session_state.target

        st.info(
            "Hint: The number is "
            + ("even." if target % 2 == 0 else "odd.")
        )

        save_stats()

    else:
        st.warning("Not enough coins!")


# ==========================================
# STATISTICS
# ==========================================

st.divider()
st.header("📊 Your Statistics")

col1, col2, col3, col4 = st.columns(4)

col1.metric("⭐ Score", st.session_state.score)
col2.metric("🪙 Coins", st.session_state.coins)
col3.metric("🏆 Games Won", st.session_state.games_won)
col4.metric(
    "🎯 Levels Completed",
    st.session_state.levels_completed
)

st.caption(
    "Keep playing to improve your score and climb the leaderboard!"
)
