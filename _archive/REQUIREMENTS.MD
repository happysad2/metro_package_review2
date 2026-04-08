Create an app to review packages for sydney metro:

Should be broken into three modeles fore easy maintainability.
1. asset register checker.
2. ifc checker.
3. nwc checker.

for each there should be three tiers:
- granual per module - eg asset register check, nwc check, ifc check- sheets etc of individual findings, pass fails and reasons.
- individiaal summary per module - so it is a high-level of eg. 300 words or less.
- high-level for all three collated - 300 words or less across entire package in concise language.

the 'orchestrator' is the module that collates all of this from the granular and high level summaries. the high level should have:
1. guidance on where to look as the reviewer (very short)
2. comments ready to populate < 300 words on entire package.

- wrap this in a UI, with the images linked.
- input folder - the package containing nwc, asset reg, ifc.
- output folder - high-level comments output.
- user loads files into the input folder manually
- outputs are put in output folder and log in the UI.

UI direction
- the UI should be slick and tailored without other logos etc or stock kits.
- should be 'Sydney Metro Package Review'
- the outputs should be both txt and in the log summary in the checker.

The UI should have a nice transparent background of the train image.

the app should be called Metro Package Review 1.0




