
import streamlit as st
import random

st.title("🎮 My Number Guessing Game")

# Level ranges
ranges = [
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

# Start game
if "number" not in st.session_state:
    st.session_state.level = 1
    st.session_state.score = 0
    st.session_state.attempts = 3
    st.session_state.message = "Welcome! Guess the number!"
    st.session_state.number = random.randint(1, 10)
    st.session_state.finished = False

# Get current level range
level = st.session_state.level
min_number, max_number = ranges[level - 1]

st.header(f"⭐ Level {level}")
st.write(f"Guess a number between {min_number} and {max_number}")
st.write("Attempts left:", st.session_state.attempts)
st.write("Score:", st.session_state.score)

st.info(st.session_state.message)

if not st.session_state.finished:
    guess = st.number_input(
        "Enter your guess",
        min_value=min_number,
        max_value=max_number,
        step=1
    )

    if st.button("Guess"):
        if guess == st.session_state.number:
            st.session_state.score += 10

            if level == 10:
                st.session_state.message = "🏆 YOU COMPLETED ALL 10 LEVELS!"
                st.session_state.finished = True
            else:
                st.session_state.level += 1
                st.session_state.attempts = 3 + (st.session_state.level - 1) * 2

                new_min, new_max = ranges[st.session_state.level - 1]
                st.session_state.number = random.randint(new_min, new_max)
                st.session_state.message = "🎉 Correct! You unlocked the next level!"

        else:
            st.session_state.attempts -= 1

            if st.session_state.attempts == 0:
                st.session_state.level = 1
                st.session_state.score = 0
                st.session_state.attempts = 3
                st.session_state.number = random.randint(1, 10)
                st.session_state.message = "Game over! Back to Level 1!"

            elif guess < st.session_state.number:
                st.session_state.message = "Too low! Try again!"
            else:
                st.session_state.message = "Too high! Try again!"

        st.rerun()

if st.session_state.finished:
    if st.button("Play Again"):
        st.session_state.level = 1
        st.session_state.score = 0
        st.session_state.attempts = 3
        st.session_state.number = random.randint(1, 10)
        st.session_state.message = "New game! Good luck!"
        st.session_state.finished = False
        st.rerun()
