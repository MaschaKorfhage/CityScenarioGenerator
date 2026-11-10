// Combined candidate query; review OSM tags before importing.
[out:json][timeout:60];
{{geocodeArea:Bautzen}}->.searchArea;
(
  // Local Recreational Area
  nwr[leisure="park"](area.searchArea);
  nwr[leisure="recreation_ground"](area.searchArea);
  // Bicycle Route
  relation[route="bicycle"](area.searchArea);
  // Flea Market Location
  nwr[marketplace="flea_market"](area.searchArea);
  nwr[shop="flea_market"](area.searchArea);
  // Singing School
  nwr[amenity="music_school"][subject="singing"](area.searchArea);
  // Fishing Location
  nwr[leisure="fishing"](area.searchArea);
  nwr[sport="fishing"](area.searchArea);
  // Concert House
  nwr[amenity="concert_hall"](area.searchArea);
  nwr[building="concert_hall"](area.searchArea);
  // Car Wash
  nwr[amenity="car_wash"](area.searchArea);
  // Bow Range
  nwr[leisure="archery"](area.searchArea);
  nwr[sport="archery"](area.searchArea);
  // Hiking Location
  relation[route="hiking"](area.searchArea);
  // Golf Club
  nwr[leisure="golf_course"](area.searchArea);
  // Horse Stable
  nwr[leisure="horse_riding"](area.searchArea);
  nwr[building="stable"](area.searchArea);
  nwr[building="riding_hall"](area.searchArea);
  // Running Path
  relation[route="running"](area.searchArea);
  nwr[sport="running"](area.searchArea);
  // Hunting Forest
  nwr[landuse="forest"][hunting="yes"](area.searchArea);
  // Fitness Studio
  nwr[leisure="fitness_centre"](area.searchArea);
  nwr[amenity="gym"](area.searchArea);
  // Yoga Studio
  nwr[sport="yoga"](area.searchArea);
  nwr[leisure="yoga"](area.searchArea);
  // Outdoor Swimming Pool
  nwr[leisure="swimming_pool"](area.searchArea);
  // Walking Location
  relation[route="foot"](area.searchArea);
  relation[route="walking"](area.searchArea);
  // Musical Society
  nwr[amenity="music_school"](area.searchArea);
  nwr[club="music"](area.searchArea);
  // Festival Location
  nwr[leisure="festival_grounds"](area.searchArea);
  nwr[amenity="events_venue"](area.searchArea);
  // Community College
  nwr[amenity="college"](area.searchArea);
  nwr[building="college"](area.searchArea);
  // Soccer Practice Location
  nwr[leisure="pitch"][sport="soccer"](area.searchArea);
  nwr[leisure="sports_centre"][sport="soccer"](area.searchArea);
  // Mountain Road
  relation[route="mtb"](area.searchArea);
  way[highway="track"](area.searchArea);
);
out center tags;
