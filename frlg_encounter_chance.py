import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-er', '--encounter_rate', type=int, default=21, help='base encounter rate of area. Found in wild_encounters.json')
parser.add_argument('-nbs', '--new_bush_steps', type=int, nargs='*', default=[1], 
    help='step numbers at which grass is entered. e.g for route 1, if no encounters are hit, new bushes are entered at steps  1, 6, 9, 13 and 17')
parser.add_argument('-msc', '--max_step_count', type=int, default=200,
    help='max number of steps to calculate percentages for')

args = parser.parse_args()

base_encounter_rate = args.encounter_rate
new_bush_steps = args.new_bush_steps
max_step_count = args.max_step_count

class Universe():
    def __init__(self, encounter_buff, probability, hit_encounter):
        # the encounter buff value. Universes with equal encounter_buff values
        # are essentially equivalent, and will be merged.
        self.encounter_buff = encounter_buff
        # the probability that we reach this 'universe'
        self.probability = probability
        # if we hit an encounter in this universe
        self.hit_encounter = hit_encounter

class TileResult():
    def __init__(self, encounter_chance, cumulative_chance, exact_tile_chance):
        # the percent chance that we get an encounter on this tile, given that we have
        # not gotten an encounter on any of the previous tiles
        self.encounter_chance = encounter_chance
        # the percent chance that we get an encounter on or before this tile
        self.cumulative_chance = cumulative_chance
        # the chance that we get an encounter on exactly this tile
        self.exact_chance = exact_tile_chance

def get_encounter_rate(base_encounter_rate, encounter_buff):
    encounter_rate = base_encounter_rate * 16
    encounter_rate += encounter_buff * 16 // 200
    if encounter_rate > 1600:
        encounter_rate = 1600
    return encounter_rate / 1600

def get_new_universes(universe, step_count, protected_step_count):
    new_universes = []

    encounter_rate = get_encounter_rate(base_encounter_rate, universe.encounter_buff)
    no_encounter_rate = 1.0 - encounter_rate
    if step_count <= protected_step_count:
        # universe where the we skip the standard encounter check (95%)
        new_universes.append(Universe(universe.encounter_buff, universe.probability * 0.95, False))

        if step_count in new_bush_steps: # we enter a new bush on this step
            # universe where we do the check on a protected roll, but get protected
            # by the grass transition 5% * 40% = 2%
            new_universes.append(Universe(universe.encounter_buff, universe.probability * 0.02, False))

            # universe where we roll for an encounter on a protected tile, and don't get one.
            # 5% * 60% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * 0.03 * no_encounter_rate, False))

            # universe where we roll for an encounter on a protected tile, and get it
            # 5% * 60% * encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * 0.03 * encounter_rate, True))

        else: # not entering a new bush
            # universe where we roll for an encounter on a protected tile, and don't get one.
            # 5% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * 0.05 * no_encounter_rate, False))

            # universe where we roll for an encounter on a protected tile, and get it
            # 5% * encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * 0.05 * encounter_rate, True))

    else: # unprotected steps
        if step_count in new_bush_steps: # we enter a new bush on this step
            # universe where  get protected the grass transition - 40%
            new_universes.append(Universe(universe.encounter_buff, universe.probability * 0.40, False))

            # universe where we roll for an encounter, and don't get one.
            # 60% * no_encounter_rate
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * 0.60 * no_encounter_rate, False))

            # universe where we roll for an encounter on a protected tile, and get it
            # 60% * encounter_rate
            new_universes.append(Universe(universe.encounter_buff, universe.probability * 0.60 * encounter_rate, True))

        else: # not entering a new bush
            # universe where don't get an encounter
            # no_encounter_rate%
            new_universes.append(Universe(universe.encounter_buff + base_encounter_rate, universe.probability * no_encounter_rate, False))

            # universe where we get an encounter
            # encounter_rate%
            new_universes.append(Universe(universe.encounter_buff, universe.probability * encounter_rate, True))

    return new_universes

def get_tile_result(universes, cumulative_chance):
    exact_chance = 0.0
    encounter_prob = 0.0 # TODO: Figure out to calculate this

    for universe in universes:
        if universe.hit_encounter:
            exact_chance += universe.probability
    
    return TileResult(encounter_prob, cumulative_chance + exact_chance, exact_chance)

def trim_and_merge_universes(universes):
    buff_to_universe = {}

    for universe in universes:
        if not universe.hit_encounter: # get rid of all universes where we hit an encounter

            if (universe.probability > 0.0):
                # universes with the same encounter_buff value can be merged into one universe
                # the new universe's probability is the sum of all the smaller universes' probabilities.
                if  universe.encounter_buff in buff_to_universe:
                    buff_to_universe[universe.encounter_buff].probability += universe.probability
                else:
                    buff_to_universe[universe.encounter_buff] = universe
    
    return list(buff_to_universe.values())

# start with one universe, new branches will be created at each step
universes = []
universes.append(Universe(0, 1.0, False))

cumulative_chance = 0.0
step_count = 1
protected_step_count = max(0, 8 - (base_encounter_rate // 10))
while cumulative_chance < 0.9999 and step_count <= max_step_count:
    new_universes = []
    for universe in universes:
        new_universes.extend(get_new_universes(universe, step_count, protected_step_count))
    
    tile_result = get_tile_result(new_universes, cumulative_chance)
    print("Tile: {:d} Exact Chance: {:.4f} Cumulative Chance: {:.4f}".format(step_count, tile_result.exact_chance, tile_result.cumulative_chance))
    
    cumulative_chance = tile_result.cumulative_chance
    universes = trim_and_merge_universes(new_universes)
    step_count += 1

        
