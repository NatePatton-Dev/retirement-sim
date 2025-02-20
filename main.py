# Would like to input current pre-retirement numbers eventually, and have monte carlo go through pre and post retirement, but this will involve sims within sims, and lots of other unknowns
# would also like to be able to input other retirement accounts like taxable income etc, but I already have some stuff arouund tax optimization for my case in here that I'd need to lose for this to be useable by anyone

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def get_user_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ")
    return float(user_input) if user_input.strip() else default
    # should add a check for valid input here? needs to be a number, might error automatically, test this

# User-Defined Inputs
print("Enter your retirement assumptions (press Enter to keep defaults):")
start_year = int(get_user_input("Year of retirement start", 2051))
#end_year = int(get_user_input("Year to end simulation", 2101))
end_year = int(start_year + 50)
age_start = int(get_user_input("Age at retirement", 55))
inflation_rate = get_user_input("Expected annual inflation rate", 0.03)
ss_cola_factor = get_user_input("Social Security COLA as a percentage of inflation", 0.80)

# Investment assumptions
# ideally have these get calculated based on % bonds needed for x years based on approach to Social security, should be able to calculate balances, what percent of balance should be bonds based on needed income, and calculate these per year in sim
equity_return_initial = get_user_input("Initial expected nominal return on investments including 10 years of bonds, the rest in stocks", 0.06)
# annual_equity_increase = get_user_input("Annual increase in equity return as bonds are dropped from portfolio", 0.002)
full_equity_return = get_user_input("Expected nominal return when fully invested in stocks", 0.08)
transition_years = int(get_user_input("Years over which equity return transitions to full return, or the number of years worth of income carried in bonds prior to receiving social security", 10))
annual_equity_increase = float((full_equity_return - equity_return_initial)/transition_years)

# Fixed Income Sources
# SS optimization would be cool here, but I would need a tool that can accurately calculate different SS payouts of both spouses at different ages
ss_start_age = int(get_user_input("Age at which Social Security begins", 68)) # - default 68 expecting 68 to be the earliest retirement age available, and what SS calculator gives data for
ss_income = get_user_input("Initial Social Security income per year", 128000)
wrs_pension = get_user_input("Initial WRS pension per year", 206000)
extra_fixed_income = get_user_input("Additional fixed income sources per year", 11500)

# Investment Balances
# These would be pulled from existing pre-retirement data 
trad_wdc_balance = get_user_input("Traditional WDC account balance at retirement", 1595000)
roth_wdc_balance = get_user_input("Roth WDC account balance at retirement", 2491000)

# Income Needs (Adjusted for 25 years of inflation)
total_income_needed = get_user_input("2025 dollars initial annual income needed at retirement", 134000) * (1 + inflation_rate) ** 25

# Standard Deduction (Adjusted for 25 years of inflation)
inital_standard_deduction = get_user_input("2025 Standard deduction for tax calculations", 30000) * (1 + inflation_rate) ** 25

def adjust_standard_deduction(years_since_start):
    return initial_standard_deduction * (1 + inflation_rate) ** years_since_start

# Tax Brackets (User Input)
def get_tax_brackets(tax_type, default_brackets):
    print(f"Enter {tax_type} tax brackets in 2025 dollars as rate, threshold (comma-separated). Type 'done' when finished:")
    print("Example format: 0.10, 22000")
    print("Defaults are already entered.")
    brackets = []
    while True:
        user_input = input()
        if user_input.lower() == 'done' or not user_input.strip():
            break
        try:
            rate, threshold = map(float, user_input.split(","))
            brackets.append((rate, threshold * (1 + inflation_rate) ** 25))
        except ValueError:
            print("Invalid input. Please enter in format: rate, threshold")
    return brackets if brackets else [(rate, threshold * (1 + inflation_rate) ** 25) for rate, threshold in default_brackets]

# Default tax brackets
default_federal_brackets = [(0.10, 23200), (0.12, 94300), (0.22, 201050), (0.24, 383900)]
default_wi_brackets = [(0.035, 19090), (0.0465, 38190), (0.0627, 420420)]

print("Federal tax brackets:")
federal_brackets = get_tax_brackets("Federal", default_federal_brackets)
print("Wisconsin state tax brackets:")
wi_brackets = get_tax_brackets("Wisconsin", default_wi_brackets)

# Remove standard deduction from calculate_tax() because it will always be included in taxable_income
def calculate_tax(income, brackets, inflation_rate, years, standard_deduction):
    adjusted_standard_deduction = standard_deduction * (1 + inflation_rate) ** years  # Adjust standard deduction for inflation over time
    taxable_income = max(0, income - adjusted_standard_deduction)
    adjusted_brackets = [(rate, threshold * (1 + inflation_rate) ** years) for rate, threshold in brackets]
    tax = 0
    prev_threshold = 0
    for rate, threshold in adjusted_brackets:
        if taxable_income > threshold:
            tax += (threshold - prev_threshold) * rate
            prev_threshold = threshold
        else:
            tax += (taxable_income - prev_threshold) * rate
            break
    return tax

# Monte Carlo simulation parameters
num_simulations = 1000
market_volatility = 0.15

success_count = 0
data = []

for sim in range(num_simulations):
    sim_data = []
    trad_balance = trad_wdc_balance
    roth_balance = roth_wdc_balance
    annual_income_needed = total_income_needed
    success = True

    for year in range(start_year, end_year + 1):
        age = age_start + (year - start_year)
        years_since_start = year - start_year

        if age < ss_start_age:
            equity_return = equity_return_initial + (min(years_since_start+3, transition_years+3) * annual_equity_increase) # delay of 3 years before I start dropping bonds
        else:
            equity_return = full_equity_return

        random_return = np.random.normal(equity_return, market_volatility)

        if age >= ss_start_age:
            ss_income *= (1 + inflation_rate * ss_cola_factor)

        wrs_adjustment = np.random.normal(equity_return, market_volatility)
        wrs_pension *= (1 + wrs_adjustment)

        if years_since_start < 10:
            extra_fixed_income *= (1 + inflation_rate)
        else:
            extra_fixed_income = 0  # Stop extra_fixed_income after 10 years

        standard_deduction = adjust_standard_deduction(years_since_start)
        total_fixed_income = (ss_income if age >= ss_start_age else 0) + wrs_pension + extra_fixed_income

        taxable_ss = ss_income * 0.85 if age >= ss_start_age else 0
        taxable_income = max(0, taxable_ss + wrs_pension + extra_fixed_income - standard_deduction)
        
        additional_needed = max(0, annual_income_needed - total_fixed_income) # i think i should calculate net income and be subtracting that from annual-income-needed here
        trad_withdrawal = 0
        remaining_needed = additional_needed

        # figure out how to prioritize using up 12% tax bracket here, and doing all trad from 55-59, and include state brackets in this - maybe combine brackets?, if trad runs out before 60, fail, if trad runs out after 60 stop at 0 and go to roth ---------
        for rate, threshold in federal_brackets:
            if remaining_needed > 0:
                taxable_withdrawal = min(remaining_needed, threshold - taxable_income)
                trad_withdrawal += taxable_withdrawal / (1 - rate)
                taxable_income += taxable_withdrawal
                remaining_needed -= taxable_withdrawal
        
        roth_withdrawal = max(0, additional_needed - trad_withdrawal)  #calculate what i should subtract from additiona_needed here ------------------------------------

        # if roth balance would drop to 0, go back to trad withdrawals if needed

        federal_tax = calculate_tax(taxable_income, federal_brackets, inflation_rate, years_since_start, standard_deduction)
        wi_tax = calculate_tax(taxable_income, wi_brackets, inflation_rate, years_since_start, standard_deduction)
        tax_due = federal_tax + wi_tax
        after_tax_total_income = total_fixed_income + trad_withdrawal - tax_due      

        trad_balance -= trad_withdrawal
        roth_balance -= roth_withdrawal

        if trad_balance <= 0 and roth_balance <= 0:
            success = False
            break

        annual_income_needed *= (1 + inflation_rate)
        standard_deduction *= (1 + inflation_rate)      
        trad_balance *= (1 + random_return)
        roth_balance *= (1 + random_return)        

        sim_data.append([year, age, trad_balance, roth_balance, total_fixed_income, taxable_income])


    if success:
        success_count += 1
    data.append(sim_data)

success_rate = success_count / num_simulations * 100
print(f"Retirement success rate: {success_rate:.2f}%")
