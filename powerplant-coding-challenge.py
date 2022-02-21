from flask import Flask
from flask_restful import Resource, Api, reqparse
import json

app = Flask(__name__)
api = Api(app)

plan_post_args = reqparse.RequestParser()
plan_post_args.add_argument("load", type=float)
plan_post_args.add_argument("fuels")
plan_post_args.add_argument("powerplants", action='append')

fuels_post_args = reqparse.RequestParser()
fuels_post_args.add_argument("gas(euro/MWh)", type=float)
fuels_post_args.add_argument("kerosine(euro/MWh)", type=float)
fuels_post_args.add_argument("co2(euro/ton)", type=float)
fuels_post_args.add_argument("wind(%)", type=float)


class Test(Resource):
    def post (self):
        ##data initialization
        actual_load = 0
        args = plan_post_args.parse_args()
        args["fuels"] = json.loads(args["fuels"].replace("'", "\""))
        temp_array = []
        ##energy dictionnary to be able to iterate later on all the energy beside the wind based energy
        energy_dict = {"gas(euro/MWh)" : "gasfired", "kerosine(euro/MWh)" : "turbojet"}
        counter = 0
        response_json = []
        for x in args["powerplants"]:
            temp_array.append(json.loads(args["powerplants"][counter].replace("'", "\"")))
            counter = counter + 1
        args["powerplants"] = temp_array

        ##as the wind turbine are "free to run", will always count them at maximal possible value
        indexes = [i for i,x in enumerate(args["powerplants"]) if x["type"] == 'windturbine']
        for x in indexes:
            actual_load = actual_load + ( round(args["powerplants"][x]["pmax"]*(args["fuels"]["wind(%)"]*0.01), 1))
            response_json.append({"name": args["powerplants"][x]["name"], "p": round(args["powerplants"][x]["pmax"]*(args["fuels"]["wind(%)"]*0.01),1)})
        
        ##create an array with all the others fuels
        fuels_subarray = []
        for x in args["fuels"]:
            if x != "co2(euro/ton)" and x != "wind(%)":
                fuels_subarray.append(args["fuels"][x])
        lowest_cost = {"price" : 0, "name" : ""}

        ##make a while to iterate through all the differents fuels
        while len(fuels_subarray) != 0:
            ##look for the fuel with the lowest cost, and create an array with all the indexes of corresponding powerplants
            lowest_cost["price"] = min(fuels_subarray)
            for x in args["fuels"]:
                if args["fuels"][x] == lowest_cost["price"]:
                    lowest_cost["name"] = x   
            indexes = [i for i,j in enumerate(args["powerplants"]) if j["type"] == energy_dict[lowest_cost["name"]]]
            pmax_energy = 0
            pmin_energy = 0
            ranking_lowest_pmin = []

            ##iterate through all the concerned powerplants
            for x in indexes:
                ##create reference data to take into account the maximal and the minimal total output of thoses powerplants
                pmax_energy = pmax_energy + args["powerplants"][x]["pmax"]
                pmin_energy = pmin_energy + args["powerplants"][x]["pmin"]
                ##create an array to determine the powerplant with the lowest output to be able to change its output value if needed
                if len(ranking_lowest_pmin) == 0:
                    ranking_lowest_pmin.append(args["powerplants"][x])
                else:
                    y = 0
                    not_inserted = True
                    while y < len(ranking_lowest_pmin) and not_inserted:
                        if ranking_lowest_pmin[y]["pmin"] <= args["powerplants"][x]["pmin"]:
                            ranking_lowest_pmin.insert(y, args["powerplants"][x])
                            not_inserted = False
                        y = y+1
                    if(not_inserted):
                        ranking_lowest_pmin.append(args["powerplants"][x])
            ##look at if the maximal output of the current powerplant type is greater than the wanted load
            if (pmax_energy + actual_load) > args["load"]:
                ##look at the case where the previous operation is true because of the fact that the desired load is already not reached
                if(actual_load != args["load"]):
                    temp_array = []
                    temp_load = 0

                    ##in the case the minimal total output of the powerplants of this type is too much for the desired load, just get rid of some (or all) of
                    ##this powerplant type in order to try to reach the desired total load perfectly
                    if ( pmin_energy >= (args["load"]-actual_load)):
                        for x in range(len(indexes)):
                            if((pmin_energy-ranking_lowest_pmin[0]["pmin"]) >= (args["load"]-actual_load)):
                                response_json.append({"name": ranking_lowest_pmin[0]["name"], "p": 0 })
                                if args["powerplants"][x]["name"] == ranking_lowest_pmin[0]["name"]:
                                    indexes.remove(indexes[x])

                    ##iterate throught the remaining powerplants
                    for x in indexes:
                        ##prepare all the power needed from each powerplant, but scaled on the maximum output of the powerplant compared to others powerplants of this type
                        ##in order to not overload a given powerplant when the others can still give more output
                        load_added = round((args["load"]-actual_load)*args["powerplants"][x]["pmax"]/pmax_energy,1)
                        temp_array.append({"p":load_added, "name":args["powerplants"][x]["name"]})
                        temp_load = round(temp_load + load_added,1)

                    ##check if the sum of the power from these powerplants type is greater that the total overload
                    ##can happen because all the values are rounded, so we can have a final value that is greater than the one aimed
                    if (temp_load + actual_load) > args["load"]:
                        ##if the value is greater, we'll take some power from the powerplant with the lower maximal ouput value 
                        for y in range(len(temp_array)):
                            if ranking_lowest_pmin[-1]["name"] == temp_array[y]["name"]:
                                temp_array[y]["p"] = temp_array[y]["p"] - round(((actual_load+temp_load)-args["load"]),1)
                    
                    ##once all of these are checked, we can count the value in the total load value that will be asked from all the powerplants
                    ##and record the individual value from all powerplants for this fuel type
                    for y in temp_array:
                        actual_load = round((actual_load + y["p"]),1)
                        response_json.append({"name": y["name"], "p": y["p"]})
                
                ##in  the case the wanted load is already achieved, do not activate these poweplants
                else:
                    for x in indexes:
                        response_json.append({"name": args["powerplants"][x]["name"], "p": 0})
            
            ##in the case the total load with the maximum output value from this type's powerplants is lower or reach perfectly the wanted total load
            ##just add directly the maximum output of all those powerplants
            elif (pmax_energy + actual_load) <= args["load"]:
                for x in indexes:
                    actual_load = actual_load + args["powerplants"][x]["pmax"]
                    response_json.append({"name": args["powerplants"][x]["name"], "p": args["powerplants"][x]["pmax"]})
            
            ##remove the fuel we just got throught from the fuels list we're working on
            fuels_subarray.remove(min(fuels_subarray))

        ##once everything is done return the json with all the desired values
        return response_json

api.add_resource(Test, '/productionplan')


if __name__ == '__main__':
    ##make the api run on the desired port
    app.run(host="localhost", port=8888)