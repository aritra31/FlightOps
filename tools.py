import serpapi
from langchain.tools import tool
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta

load_dotenv()

client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))

## In-memory cache: keyed by (engine params as frozen string)
_cache = {}


def _cache_key(params: dict) -> str:
    filtered = {k: v for k, v in params.items()}
    return json.dumps(filtered, sort_keys=True)


def cached_search(params: dict) -> dict:
    key = _cache_key(params)
    if key in _cache:
        return _cache[key]
    result = client.search(params)
    _cache[key] = result
    return result


def parse_flights(results: dict, max_results: int = 5) -> list:
    all_flights = results.get("best_flights", []) + results.get("other_flights", [])
    flights = []

    for flight in all_flights[:max_results]:
        try:
            legs = flight.get("flights", [])
            if not legs:
                continue
            first_leg = legs[0]
            last_leg = legs[-1]
            flights.append({
                "price": f"${flight.get('price', 'N/A')}",
                "airline": first_leg.get("airline", "Unknown"),
                "departure": first_leg.get("departure_airport", {}).get("time", "N/A"),
                "arrival": last_leg.get("arrival_airport", {}).get("time", "N/A"),
                "duration": f"{flight.get('total_duration', 0) // 60}h {flight.get('total_duration', 0) % 60}m",
                "stops": len(legs) - 1
            })
        except Exception:
            continue

    return flights


@tool
def search_flights(origin: str, destination: str, departure_date: str,
                   trip_type: str = "one_way", return_date: str = None, adults: int = 1) -> str:
    """
    Search for available flights between two airports on a given date.
    Use this when the user wants to find flights on a specific route.
    origin: IATA airport code e.g. BOS for Boston, JFK for New York
    destination: IATA airport code e.g. MIA for Miami, LAX for Los Angeles
    departure_date: date in YYYY-MM-DD format
    trip_type: 'one_way' or 'round_trip'
    return_date: YYYY-MM-DD format, only needed if trip_type is round_trip
    adults: number of passengers, default 1
    Return the top 5 cheapest flights with price, airline, departure time, arrival time, duration and stops.
    """
    try:
        params = {
            "engine": "google_flights",
            "departure_id": origin.upper(),
            "arrival_id": destination.upper(),
            "outbound_date": departure_date,
            "currency": "USD",
            "hl": "en",
            "adults": adults,
            "type": "1" if trip_type == "round_trip" else "2"
        }

        if trip_type == "round_trip" and return_date:
            params["return_date"] = return_date

        results = cached_search(params)

        if "error" in results:
            return f"Search error: {results['error']}"

        flights = parse_flights(results)

        if not flights:
            return "No flights found for this route and date. Try a different date or route."

        return json.dumps({
            "route": f"{origin.upper()} to {destination.upper()}",
            "date": departure_date,
            "trip_type": trip_type,
            "results": flights
        }, indent=2)

    except Exception as e:
        return f"Error: {str(e)}"


@tool
def find_cheapest_dates(origin: str, destination: str, travel_month: str,
                        trip_type: str = "one_way") -> str:
    """
    Find the cheapest dates to fly a specific route within a given month.
    Use this when the user wants to know the best time to fly or wants flexible dates.
    origin: IATA airport code e.g. BOS
    destination: IATA airport code e.g. MIA
    travel_month: month in YYYY-MM format e.g. 2026-06 for June 2026
    trip_type: 'one_way' or 'round_trip'
    Return the 3 cheapest dates with their prices for that route.
    """
    try:
        year, month = int(travel_month[:4]), int(travel_month[5:7])
        start = datetime(year, month, 1)
        dates_to_check = []
        current = start

        while current.month == month:
            dates_to_check.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=3)

        results_by_date = []

        for date in dates_to_check:
            try:
                params = {
                    "engine": "google_flights",
                    "departure_id": origin.upper(),
                    "arrival_id": destination.upper(),
                    "outbound_date": date,
                    "currency": "USD",
                    "hl": "en",
                    "type": "1" if trip_type == "round_trip" else "2"
                }

                if trip_type == "round_trip":
                    return_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=7)
                    params["return_date"] = return_dt.strftime("%Y-%m-%d")

                data = cached_search(params)
                all_flights = data.get("best_flights", []) + data.get("other_flights", [])

                if all_flights:
                    cheapest = min(all_flights, key=lambda x: x.get("price", 9999))
                    price = cheapest.get("price")
                    if price:
                        results_by_date.append({"date": date, "price": price})

            except Exception:
                continue

        if not results_by_date:
            return "Could not retrieve pricing for this month. Try a different month."

        results_by_date.sort(key=lambda x: x["price"])
        top3 = results_by_date[:3]

        return json.dumps({
            "route": f"{origin.upper()} to {destination.upper()}",
            "month": travel_month,
            "cheapest_dates": [{"date": r["date"], "price": f"${r['price']}"} for r in top3]
        }, indent=2)

    except Exception as e:
        return f"Error: {str(e)}"


@tool
def compare_routes(origins: str, destinations: str, departure_date: str,
                   trip_type: str = "one_way", return_date: str = None) -> str:
    """
    Compare flights across multiple origins and destinations and rank by price.
    Use this when the user wants to compare different routes or see which combination is cheapest.
    origins: comma-separated IATA airport codes e.g. "BOS,JFK"
    destinations: comma-separated IATA airport codes e.g. "MIA,LAX,ORD"
    departure_date: date in YYYY-MM-DD format
    trip_type: 'one_way' or 'round_trip'
    return_date: YYYY-MM-DD format, only needed if trip_type is round_trip
    Return all route combinations ranked from cheapest to most expensive.
    """
    try:
        origin_list = [o.strip().upper() for o in origins.split(",")]
        dest_list = [d.strip().upper() for d in destinations.split(",")]
        all_routes = []

        for origin in origin_list:
            for destination in dest_list:
                if origin == destination:
                    continue
                try:
                    params = {
                        "engine": "google_flights",
                        "departure_id": origin,
                        "arrival_id": destination,
                        "outbound_date": departure_date,
                        "currency": "USD",
                        "hl": "en",
                        "type": "1" if trip_type == "round_trip" else "2"
                    }

                    if trip_type == "round_trip" and return_date:
                        params["return_date"] = return_date

                    data = cached_search(params)
                    all_flights = data.get("best_flights", []) + data.get("other_flights", [])

                    if all_flights:
                        cheapest = min(all_flights, key=lambda x: x.get("price", 9999))
                        price = cheapest.get("price", 9999)
                        airline = cheapest.get("flights", [{}])[0].get("airline", "Unknown")
                        legs = cheapest.get("flights", [])
                        duration = f"{cheapest.get('total_duration', 0) // 60}h {cheapest.get('total_duration', 0) % 60}m"
                        stops = len(legs) - 1

                        all_routes.append({
                            "route": f"{origin} → {destination}",
                            "price": price,
                            "price_display": f"${price}",
                            "airline": airline,
                            "duration": duration,
                            "stops": stops
                        })

                except Exception:
                    continue

        if not all_routes:
            return "No flights found for the provided routes and date."

        all_routes.sort(key=lambda x: x["price"])

        for r in all_routes:
            del r["price"]

        return json.dumps({
            "date": departure_date,
            "trip_type": trip_type,
            "routes_compared": len(all_routes),
            "ranked_by_price": all_routes
        }, indent=2)

    except Exception as e:
        return f"Error: {str(e)}"