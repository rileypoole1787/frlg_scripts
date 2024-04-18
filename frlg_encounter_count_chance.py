import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-er', '--encounter_rate', type=int, default=21, help='base encounter rate of area. Found in wild_encounters.json')
parser.add_argument('-nbs', '--new_bush_tiles', type=int, nargs='*', default=[1], 
    help='tiles at which a new patch grass is entered. e.g for route 1, if no encounters are hit, new bushes are entered at steps  1, 6, 9, 13 and 17')
parser.add_argument('-sc', '--step_count', type=int, default=200, required=True,
    help='the number of steps to calculate percentages for')
# TODO actually handle this case. Ignoring it should only have a minor effect
parser.add_argument('-est', '--extra_step_tiles', type=int, nargs='*', default=[],
    help='tiles where an encounter requires you to take an extra step/turn-frame (e.g. the left-down turn in Viridian Forest)')
parser.add_argument('-prt', '--protection-reset-tiles', type=int, nargs='*', default=[],
    help='tiles where protection should be reset. Useful if want to calculate chances for multiple passes of the same route (e.g. route one)')

# command for calculating route one chances after two passes. Assumes you always go left out of
# grass on second to last grass patch.
# python .\frlg_encounter_count_chance.py -er 21 -sc 42 -nbs 1 6 9 13 17 22 27 30 34 38 -prt 22

args = parser.parse_args()

base_encounter_rate = args.encounter_rate
new_bush_tiles = args.new_bush_tiles
max_step_count = args.step_count
extra_step_tiles = args.extra_step_tiles
protection_reset_tiles = args.protection_reset_tiles
protected_step_count = max(0, 8 - (base_encounter_rate // 10))

class Universe():
    def __init__(self, encounter_buff, probability, protected_steps_left, encounter_count):
        # the encounter buff value. Universes with equal encounter_buff values
        # are essentially equivalent, and will be merged.
        self.encounter_buff = encounter_buff
        # the probability that we reach this 'universe'
        self.probability = probability
        # number of protected steps left for this universe
        self.protected_steps_left = protected_steps_left
        # total encounters this universe has hit
        self.encounter_count = encounter_count

def get_encounter_rate(base_encounter_rate, encounter_buff):
    encounter_rate = base_encounter_rate * 16
    encounter_rate += ((encounter_buff * 16) // 200)
    if encounter_rate > 1600:
        encounter_rate = 1600
    return encounter_rate / 1600

def get_new_universes(universe, tile_number):
    new_universes = []

    encounter_rate = get_encounter_rate(base_encounter_rate, universe.encounter_buff)
    no_encounter_rate = 1.0 - encounter_rate
    no_encounter_psc = max(universe.protected_steps_left - 1, 0)
    if (tile_number + 1) in protection_reset_tiles:
        no_encounter_psc = protected_step_count

    if universe.protected_steps_left > 0:
        # universe where the we skip the standard encounter check (95%)
        new_universes.append(Universe(universe.encounter_buff, 
                                      universe.probability * 0.95, 
                                      no_encounter_psc, 
                                      universe.encounter_count))

        if tile_number in new_bush_tiles: # we enter a new bush on this step
            # universe where we do the check on a protected roll, but get protected
            # by the grass transition 5% * 40% = 2%
            new_universes.append(Universe(universe.encounter_buff, 
                                          universe.probability * 0.02, 
                                          no_encounter_psc, 
                                          universe.encounter_count))

            # universe where we roll for an encounter on a protected tile, and don't get one.
            # 5% * 60% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, 
                                          universe.probability * 0.03 * no_encounter_rate, 
                                          no_encounter_psc, 
                                          universe.encounter_count))

            # universe where we roll for an encounter on a protected tile, and get it
            # 5% * 60% * encounter_rate
            new_universes.append(Universe(0,
                                          universe.probability * 0.03 * encounter_rate, 
                                          protected_step_count,
                                          universe.encounter_count + 1))

        else: # not entering a new bush
            # universe where we roll for an encounter on a protected tile, and don't get one.
            # 5% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, 
                                          universe.probability * 0.05 * no_encounter_rate,
                                          no_encounter_psc,
                                          universe.encounter_count))

            # universe where we roll for an encounter on a protected tile, and get it
            # 5% * encounter_rate
            new_universes.append(Universe(0,
                                          universe.probability * 0.05 * encounter_rate,
                                          protected_step_count,
                                          universe.encounter_count + 1))

    else: # unprotected steps
        if tile_number in new_bush_tiles: # we enter a new bush on this step
            # universe where  get protected by the grass transition - 40%
            new_universes.append(Universe(universe.encounter_buff,
                                          universe.probability * 0.40,
                                          no_encounter_psc,
                                          universe.encounter_count))

            # universe where we roll for an encounter, and don't get one.
            # 60% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate,
                                          universe.probability * 0.60 * no_encounter_rate,
                                          no_encounter_psc,
                                          universe.encounter_count))

            # universe where we roll for an encounter on a protected tile, and get it
            # 60% * encounter_rate
            new_universes.append(Universe(0,
                                          universe.probability * 0.60 * encounter_rate,
                                          protected_step_count,
                                          universe.encounter_count + 1))

        else: # not entering a new bush
            # universe where don't get an encounter
            # no_encounter_rate%
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate,
                                          universe.probability * no_encounter_rate,
                                          no_encounter_psc,
                                          universe.encounter_count))

            # universe where we get an encounter
            # encounter_rate%
            new_universes.append(Universe(0,
                                          universe.probability * encounter_rate,
                                          protected_step_count,
                                          universe.encounter_count + 1))

    return new_universes

def get_tile_result(universes, cumulative_chance):
    exact_chance = 0.0
    encounter_prob = 0.0 # TODO: Figure out to calculate this

    for universe in universes:
        if universe.hit_encounter:
            exact_chance += universe.probability
    
    return TileResult(encounter_prob, cumulative_chance + exact_chance, exact_chance)

def merge_universes(universes):
    id_to_universe = {}

    for universe in universes:
        universe_id = (universe.encounter_count, universe.protected_steps_left, universe.encounter_buff)

        # universes with the same encounter_buff, encounter_count, and protected_steps_left
        # can be merged into one universe. the new universe's probability is the sum of all 
        # the smaller universes' probabilities.
        if  universe_id in id_to_universe:
            id_to_universe[universe_id].probability += universe.probability
        else:
            id_to_universe[universe_id] = universe
    
    return list(id_to_universe.values())

def get_results(universes):
    encounter_count_to_chance = {}
    cumulative_chance = 0.0

    for universe in universes:
        if  universe.encounter_count in encounter_count_to_chance:
            encounter_count_to_chance[universe.encounter_count] += universe.probability
        else:
            encounter_count_to_chance[universe.encounter_count] = universe.probability

        cumulative_chance += universe.probability
    
    # the below should be close to 1.0. Because of floating point errors accumulating
    # it most likely won't be exactly 1.0
    print("Sanity check. Cumulative probability = {}".format(cumulative_chance))
    return encounter_count_to_chance

# start with one universe, new branches will be created at each step
universes = []
universes.append(Universe(0, 1.0, protected_step_count, 0))

cumulative_chance = 0.0
tile_number = 1
while tile_number <= max_step_count:
    new_universes = []
    for universe in universes:
        new_universes.extend(get_new_universes(universe, tile_number))
    
    #tile_result = get_tile_result(new_universes, cumulative_chance)
    #print("Tile: {:d} Exact Chance: {:.4f} Cumulative Chance: {:.4f}".format(step_count, tile_result.exact_chance, tile_result.cumulative_chance))
    
    universes = merge_universes(new_universes)
    tile_number += 1

results = get_results(universes)
for encounter_count, probability in results.items():
    print("{:d} - {:.4g}".format(encounter_count, probability))
        
