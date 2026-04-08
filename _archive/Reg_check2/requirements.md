This is to check the validity and compliance of an asset register submitted by an external party.

Input - an excel sheet.
Output - Pass / Fail with brief comments based on conditionals as per below.

There is an in / out folder. in contains the excel. Out is for the outputs.

The output should be a highly concise textfile. a more comprehensive logfile of the run should also go to 'out'.

Directory: C:\Users\jperry3\Documents\Reg_check2

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
d-----        18/02/2026   1:55 PM                in
d-----        18/02/2026   1:21 PM                out


Conditions and flow:

1. Check that the excel sheet is in the Metro format.

	1.1. Check cell locations:
		- "Asset Description" at H6
		- "GPS Coordinates" at T6
		- "Coordinate Datum" at AA6
		- "Uniclass Code" at J6

	1.2 Check tabs within the sheet "Standard governance", "Location Specification", "Location List - To Be Populated" exist.
	
	If any fail, then put first comments as - not in Sydney Metro Template, cells not aligning.

2. Export and convert the excel tab "Asset List - To Be Populated" to CSV. This will have more granular checks.

3. Check every cell of "Asset Description" for "system" or "systems" convert to lower to check.
	- this classifies this row, or asset, as a system.
	
	For each "non-system" row do the following checks:
		All of these have a value:
			"GPS Coordinates" - find the cell that has this then check every 'non-system' row and that it has a value beneath it.
			"Coordinate Datum" - find the cell that has this then check every 'non-system' row and that it has a value.
			"Uniclass Code" - find the cell that has this then check every 'non-system' row and that it has a value.

4. Check for all that a value is present in every asset row for:
	- "Uniclass code" at J
	- "Asset Code" at column E which is unique.
	-  "Asset Description" at column H present for every row.

If any stages fail etc. add to the log and text file concise comments. Output should be broken into 'has value' checks. and 'right template checks'

The output should be in form of:

Submission template structure has been modified. Cells not aligning.
Values missing from submission. Including but not limited to:


			


			

