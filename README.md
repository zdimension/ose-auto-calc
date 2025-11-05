# ose-auto-calc

Automatically calculates total class hours from ADE-exported ICS files

## Usage 

Clone the repository and run the script with [uv](https://docs.astral.sh/uv/getting-started/installation/). Replace the URL with yours.

```bash
git clone https://github.com/zdimension/ose-auto-calc.git
cd ose-auto-calc
echo "ICAL=https://example.com/your.ics" > .env
uv run main.py
uv run main.py --done # to only consider events that have already occurred
```

## Example Output

```
Processed 19 events
Skipped 19 future events

========================================================================================================================
HOURS SUMMARY BY CODE
========================================================================================================================

Code & Name                                              CM       TD       TP    Total hours     Total HETD
------------------------------------------------------------------------------------------------------------------------
EIEL721 - ECUE Programmation orientée objet            7        7        3.5           17.5           19.83
EIESE762 - ECUE Principes des bases de données        11        3        0             14             19.5
========================================================================================================================
TOTAL                                                 18       10        3.5           31.5           39.33
========================================================================================================================
```

## Disclaimer

This tool was 99% written by Claude Sonnet 4.5 Agent. I use it often these days to write simple, one-off scripts, whose sole purpose is one simple task. 

The initial prompt was:
```
load ICAL value from .env
fetch it (it's an ics file)
parse it
each event's description contains, at the beginning of its fifth line a code made of capital letters and digits followed by " - "
get it
then each event also has in its title either the string "TP" or "TD" or "CM". if more than one appears then it's an error, warn the user.

at the end, you show for each code the total number of hours of each category (TP/TD/CM) and the total number of fiscal hours given than one TP = 2/3 of a fiscal hour, one TD = 1, and one CM = 1.5
```
The rest was esthetic changes to the output format.