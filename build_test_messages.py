"""
Builds the labelled test set for the Boston 311 intake assistant.

60 resident messages, 15 per department, written in plain resident language.
Each row carries the department the request should be routed to, a tier
(clear or boundary) and a one line reason for the label.

The tier column exists because a single blended accuracy number hides the
thing worth reporting. Clear messages name the department's own vocabulary
(pothole, no heat, playground). Boundary messages sit on a seam between two
departments, which is where a routing model actually costs money.

Labels were first written from how Boston appears to divide this work, then
checked against the `department` field in the data itself. Four were wrong and
have been corrected here:

    m006, m015   graffiti, moved to PARK. Graffiti Removal holds 100% of its
                 volume under Parks, whether or not the surface faces a street.
    m043         rats in a park, moved to ISD. Rodent Activity holds 95% of its
                 volume under Inspectional Services, park land included.
    m059         car on a private driveway, moved to BTDT. Abandoned Vehicles
                 holds 100% of its volume under Transportation.

A label was only changed where the request type names exactly what the message
describes and the data assigns that type to one department almost without
exception. Where the type was a loose fit, or the data splits the type between
departments, the label was left alone. Changing a label to match whatever the
model picked would make the model unfalsifiable.

Those corrections move the set off 15 per department, to PWDx 13, BTDT 16,
PARK 16, ISD 15.
"""

import csv
from pathlib import Path

OUT = Path(__file__).parent / "data" / "test_messages.csv"

ROWS = [
    # ---------------------------------------------------------------- PWDx
    ("PWDx", "clear",
     "There is a pothole on Dorchester Ave right before the light that keeps getting bigger. Cars are swerving into the other lane to miss it.",
     "Street surface repair is Public Works."),
    ("PWDx", "clear",
     "My trash was not picked up this morning. The whole even side of the street got collected and ours was skipped.",
     "Household trash collection is Public Works."),
    ("PWDx", "clear",
     "Recycling has not been taken for two weeks now. The blue bins are full and people are stacking cardboard next to them.",
     "Recycling collection is Public Works."),
    ("PWDx", "clear",
     "The street lights on our block have been out since Friday. It is completely dark from the corner down to the end of the street.",
     "Street light outage is Public Works."),
    ("PWDx", "clear",
     "One of the sidewalk slabs outside my building has lifted about three inches. My neighbor tripped on it last week carrying groceries.",
     "Sidewalk repair is Public Works."),
    ("PARK", "clear",
     "Someone tagged the utility box and the mailbox on the corner with spray paint over the weekend.",
     "Graffiti Removal is Parks and Recreation in the data, holding 100% of that type's volume."),
    ("PWDx", "clear",
     "The storm drain at the bottom of my street is blocked with leaves and the water pools up past the curb every time it rains.",
     "Catch basin cleaning is Public Works."),
    ("PWDx", "clear",
     "The ramp at the crosswalk never got cleared after the storm. There is a pile of snow sitting right where the curb cut is.",
     "Snow and ice clearing on public ways is Public Works."),
    ("PWDx", "clear",
     "There is a dead raccoon in the middle of the road near the school crossing and it has been there since yesterday.",
     "Dead animal pickup is Public Works."),
    ("PWDx", "clear",
     "The sign says street sweeping is Tuesday and everyone moves their cars, but the sweeper has not come through in a month.",
     "Street cleaning is Public Works."),
    ("PWDx", "boundary",
     "Someone dumped a mattress and six bags of household junk on the public sidewalk next to the bus shelter.",
     "Dumping on a public way is Public Works. Reads like Inspectional Services because of the word dumping.",),
    ("PWDx", "boundary",
     "The street light pole on the corner is leaning badly toward the road. It looks like a car clipped it.",
     "The pole and the light are Public Works infrastructure, not a traffic device."),
    ("PWDx", "boundary",
     "There is a whole section of sidewalk missing in front of the empty lot on my street, just dirt and gravel where the concrete used to be.",
     "Sidewalk reconstruction is Public Works even where the abutting lot is private."),
    ("PWDx", "boundary",
     "The city trash barrel at the bus stop is overflowing and there is garbage blowing into the street.",
     "Public litter barrel is Public Works. Reads like Transportation because of the bus stop."),
    ("PARK", "boundary",
     "The long retaining wall along the sidewalk is covered in tags. It is the wall on the street side, not inside the park.",
     "Graffiti Removal is Parks and Recreation in the data whether or not the wall faces a street."),

    # ---------------------------------------------------------------- BTDT
    ("BTDT", "clear",
     "There is a car that has not moved in about six weeks. Two flat tires, expired plates, no sticker. It is taking up a resident spot.",
     "Abandoned vehicle is Transportation."),
    ("BTDT", "clear",
     "The parking meter on the corner took my card, charged me, and then showed zero minutes. It did the same thing to the person behind me.",
     "Parking meter repair is Transportation."),
    ("BTDT", "clear",
     "The traffic signal at the intersection is stuck on red in all directions. Drivers are just creeping through when they think it is clear.",
     "Traffic signal repair is Transportation."),
    ("BTDT", "clear",
     "The stop sign at the end of my street got knocked down and is lying in the grass. Cars are rolling straight through now.",
     "Street sign repair and replacement is Transportation."),
    ("BTDT", "clear",
     "Delivery vans park in the bike lane every single morning between eight and ten and force riders out into traffic.",
     "Parking enforcement in a bike lane is Transportation."),
    ("BTDT", "clear",
     "The crosswalk paint by the elementary school has worn down to almost nothing. You cannot see the stripes at all in the rain.",
     "Pavement markings are Transportation."),
    ("BTDT", "clear",
     "A box truck double parks in the travel lane outside the restaurant every evening and blocks the whole street.",
     "Double parking enforcement is Transportation."),
    ("BTDT", "clear",
     "I renewed my resident parking sticker online five weeks ago and it still has not come in the mail. I am getting tickets.",
     "Resident parking permits are Transportation."),
    ("BTDT", "clear",
     "The speed limit sign that used to be at the top of the hill never went back up after the construction finished.",
     "Missing regulatory signage is Transportation."),
    ("BTDT", "clear",
     "The walk button at the crossing does nothing. You press it and the signal never gives a walk phase, so people cross against traffic.",
     "Pedestrian signal repair is Transportation."),
    ("BTDT", "boundary",
     "There is a car parked right across the fire hydrant on my street and it has been there all day.",
     "Hydrant parking enforcement is Transportation. Reads like public safety."),
    ("BTDT", "boundary",
     "The blue paint and the wheelchair symbol in the accessible space outside the pharmacy are completely worn away.",
     "Accessible space markings are Transportation. Reads like Public Works because it is paint on pavement."),
    ("BTDT", "boundary",
     "Someone keeps parking fully up on the sidewalk and my mother cannot get her wheelchair past. She has to go into the road.",
     "Sidewalk parking enforcement is Transportation even though the obstruction is on a sidewalk."),
    ("BTDT", "boundary",
     "The street name sign on the pole at the corner is bent over so far it hangs into the bike lane.",
     "Street signage is Transportation, not Public Works, even though the pole is street furniture."),
    ("BTDT", "boundary",
     "Cars are parking on the grass strip at the edge of the lot by the field and churning it into mud.",
     "Parking enforcement is Transportation. Reads like Parks because of the field."),

    # ---------------------------------------------------------------- PARK
    ("PARK", "clear",
     "A big limb is hanging over the walking path after the storm. It is cracked at the trunk and still attached.",
     "Tree maintenance is Parks and Recreation."),
    ("PARK", "clear",
     "One of the swing seats at the playground is broken off and the chains are just hanging there at head height.",
     "Playground equipment is Parks and Recreation."),
    ("PARK", "clear",
     "The city tree in front of my house is dead. No leaves at all this summer and the bark is coming off in sheets.",
     "Street tree removal is Parks and Recreation."),
    ("PARK", "clear",
     "The drinking fountain in the park has not worked all season. The handle turns but nothing comes out.",
     "Park amenity repair is Parks and Recreation."),
    ("PARK", "clear",
     "The infield at the baseball field floods after every rain and stays soaked for days. Two games got called off.",
     "Athletic field maintenance is Parks and Recreation."),
    ("PARK", "clear",
     "The park bathroom is locked during the hours posted on the door. It has been locked every weekend this month.",
     "Park facility operation is Parks and Recreation."),
    ("PARK", "clear",
     "The climbing structure in the tot lot is covered in spray paint, including the slide the little kids use.",
     "Graffiti inside a park is Parks and Recreation."),
    ("PARK", "clear",
     "The rim on the basketball court is bent down at an angle and the net is gone.",
     "Court equipment is Parks and Recreation."),
    ("PARK", "clear",
     "The brush at the park entrance has grown so far over the sign that you cannot read it from the sidewalk.",
     "Grounds maintenance is Parks and Recreation."),
    ("PARK", "clear",
     "Two of the benches along the path have rotted slats and one has a board missing completely.",
     "Park furniture repair is Parks and Recreation."),
    ("PARK", "boundary",
     "The city tree outside my house needs pruning. The top branches are growing right into the wires.",
     "Tree pruning is Parks and Recreation even where utility wires are involved."),
    ("PARK", "boundary",
     "The light over the park walking path has been out for weeks. People cut through there after dark.",
     "A light inside a park is Parks and Recreation, not a street light."),
    ("ISD", "boundary",
     "There are rats running around the park near the barrels every evening. My kids have seen them twice this week.",
     "Rodent Activity is Inspectional Services in the data, holding 95% of that type's volume, park land included."),
    ("PARK", "boundary",
     "There is broken glass all through the sand at the tot lot. It looks like someone smashed bottles in there overnight.",
     "Park grounds cleaning is Parks and Recreation, not street cleaning."),
    ("PARK", "boundary",
     "The fence around the community garden got knocked down on one side and the gate is hanging off.",
     "Fencing on park land is Parks and Recreation. Reads like a private property matter."),

    # ----------------------------------------------------------------- ISD
    ("ISD", "clear",
     "We have had no heat for four days. It is in the forties at night and the landlord is not returning calls.",
     "Heat violations are Inspectional Services."),
    ("ISD", "clear",
     "No hot water anywhere in the building for over a week. Five units are affected and nobody has come to look at it.",
     "Hot water violations are Inspectional Services."),
    ("ISD", "clear",
     "There are mice in the kitchen walls. I can hear them at night and there are droppings under the sink. The landlord says it is my problem.",
     "Rodent and pest violations in housing are Inspectional Services."),
    ("ISD", "clear",
     "Water has been coming through my ceiling from the unit above for a month and there is black mold spreading across the corner now.",
     "Habitability and sanitary code violations are Inspectional Services."),
    ("ISD", "clear",
     "The basement unit next door has no windows and I count at least six people living in it. There are mattresses in what looks like a storage room.",
     "Illegal occupancy is Inspectional Services."),
    ("ISD", "clear",
     "The crew next door starts demolition at six in the morning and I have never seen a permit posted anywhere on the building.",
     "Work without a permit is Inspectional Services."),
    ("ISD", "clear",
     "The restaurant behind my building keeps trays of food out in the alley on crates for hours before service.",
     "Food establishment sanitation is Inspectional Services."),
    ("ISD", "clear",
     "Cockroaches are through the whole building, in the hallways and in the units. Management sprayed once in June and never came back.",
     "Pest infestation in housing is Inspectional Services."),
    ("ISD", "clear",
     "The landlord took the smoke detectors out of the hallway during the renovation three weeks ago and never put them back.",
     "Life safety code violations are Inspectional Services."),
    ("ISD", "clear",
     "The vacant house on the corner has broken windows and the back door is standing wide open. People are going in and out of it.",
     "Vacant and unsecured building is Inspectional Services."),
    ("ISD", "boundary",
     "The yard next door is waist high in weeds with bags of trash and a broken fridge sitting in it.",
     "Trash and overgrowth on private property is Inspectional Services, not Public Works collection."),
    ("ISD", "boundary",
     "Rats started showing up in my yard right after they opened up the ground at the construction site behind us.",
     "Rodent control at a construction site is Inspectional Services."),
    ("ISD", "boundary",
     "The business on the corner leaves its private dumpster out on the street all week and it is overflowing.",
     "Private waste storage violation is Inspectional Services. Reads like Public Works or Transportation."),
    ("BTDT", "boundary",
     "There is a car rotting in the driveway next door, up on blocks, leaking something dark onto the pavement.",
     "Abandoned Vehicles is Transportation in the data, holding 100% of that type's volume, private property included."),
    ("ISD", "boundary",
     "There is a strong sewage smell in my bathroom and the downstairs unit has it too. It has been getting worse for two weeks.",
     "Plumbing and sanitary violation inside a building is Inspectional Services, not a city sewer issue."),
]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["msg_id", "message", "true_dept", "tier", "label_reason"])
        for i, (dept, tier, message, reason) in enumerate(ROWS, start=1):
            writer.writerow([f"m{i:03d}", message, dept, tier, reason])

    print(f"wrote {OUT}  rows={len(ROWS)}")
    for dept in ["PWDx", "BTDT", "PARK", "ISD"]:
        clear = sum(1 for d, t, _, _ in ROWS if d == dept and t == "clear")
        bound = sum(1 for d, t, _, _ in ROWS if d == dept and t == "boundary")
        print(f"  {dept:5s} total={clear + bound:3d}  clear={clear:3d}  boundary={bound:3d}")


if __name__ == "__main__":
    main()
