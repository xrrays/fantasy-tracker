from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from keys import LEAGUE_ID

sc = OAuth2(None, None, from_file = 'oauth2.json')
gm = yfa.Game(sc, 'nhl')
lg = gm.to_league(LEAGUE_ID)

num_weeks = lg.current_week()  # number of weeks

# Option 1
def current_week_scoreboard():

    print("Displaying Current Week Scoreboard...")

# Option 2
def points_for_leaderboard():

    print("Displaying Points For Leaderboard...")

# Option 3
def standard_deviation_points_for():

    print("Calculating Standard Deviation for Points For...")

# Option 4
def points_against_leaderboard():

    print("Displaying Points Against Leaderboard...")

# Option 5
def standard_deviation_points_against():

    print("Calculating Standard Deviation for Points Against...")

# Option 6
def average_margin_of_victory_loss():

    print("Calculating Average Margin of Victory/Loss...")

# Option 7
def standings():

    print("Displaying Current Standings...")

# Option 8
def standings_vs_points_for_difference():

    print("Calculating Standings vs Points For Difference...")

def display_menu():
    print("Welcome to the fantasy tracker application for Peeny for Celebrini!")
    print("Choose an option:")
    print("1. Current Week Scoreboard")
    print("2. Points For Leaderboard")
    print("3. Standard Deviation for Points For")
    print("4. Points Against Leaderboard")
    print("5. Standard Deviation for Points Against")
    print("6. Average Margin of Victory/Loss")
    print("7. Standings")
    print("8. Standings vs Points For Difference")
    print("0. Exit")

def main_menu():
    while True:
        display_menu()
        choice = input("Enter your choice: ")

        if choice == '1':
            print("Fetching current week scoreboard...")
            # call function
        elif choice == '2':
            print("Fetching Points For Leaderboard...")
            # call function
        elif choice == '3':
            print("Calculating Standard Deviation for Points For...")
            # call function
        elif choice == '4':
            print("Fetching Points Against Leaderboard...")
            # call function
        elif choice == '5':
            print("Calculating Standard Deviation for Points Against...")
            # call function
        elif choice == '6':
            print("Calculating Average Margin of Victory/Loss...")
            # call function
        elif choice == '7':
            print("Fetching Standings...")
            # call function
        elif choice == '8':
            print("Calculating Standings vs Points For Difference...")
            # call function
        elif choice == '0':
            print("Exiting Fantasy Tracker App. Goodbye!")
            break
        else:
            print("Invalid choice, please select a valid option.")

main_menu()