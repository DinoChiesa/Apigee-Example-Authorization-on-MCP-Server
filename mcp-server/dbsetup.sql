-- create the tables 
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  signup_date TEXT NOT NULL
);

CREATE TABLE products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  price REAL NOT NULL,
  keywords TEXT,
  available INTEGER NOT NULL
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  order_date TEXT NOT NULL,
  status TEXT NOT NULL,
  total_amount REAL NOT NULL,
  FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE TABLE order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  FOREIGN KEY(order_id) REFERENCES orders(id),
  FOREIGN KEY(product_id) REFERENCES products(id)
);


-- insert some initial data.

-- Sample Account
INSERT INTO accounts (name, email, signup_date) VALUES
('Alice Johnson', 'alice@example.com', '2025-01-15'),
('Bob Smith', 'bob@example.com', '2024-02-20');


INSERT INTO products (id, name, description, price, keywords, available) VALUES
(123769, 'Earthquake Pills', 'Instant Earthquakes! Why wait? CAUTION: No Effect On Road-Runners.', 17.65, '["shake","quake","pills"]', 14),
(133833, 'Super speed vitamins', 'Supposedly they make you really fast! (your mileage may vary)', 32.65, '["speed","vitamins","pills"]', 64),
(134421, 'Hi-speed tonic', 'Lets one run super fast', 27.75, '["speed","drink"]', 64),
(135531, 'Jet-Propelled Pogo-Stick', 'If you want to jump high, this is what you need.', 57.35, '["jump","jet","boing"]', 51),
(137734, 'Jet Propelled Skis', 'Super fast travel on flat surfaces. Warning: brakes are not included.', 82.52, '["jet","speed","vehicle"]', 27),
(137834, 'Artificial Rock', 'Lets you become like a real rock out in the open.', 81.5, '["fake"]', 18),
(147463, 'Fake Tunnel', 'Stick on the front of a wall to give the appearance of a tunnel', 5.25, '["fake"]', 17),
(147466, 'Fake Road', 'Roll out this polyurethane surface that looks like a real road! Fool your friends!', 405.25, '["fake"]', 17),
(148463, 'Anvil', 'High quality anvil made of hardened steel for maximum weight and durability', 50, '["iron","heavy"]', 3),
(157383, 'Winch', 'Useful for raising heavy items such as anvils', 50, '["heavy","lift","raise"]', 3),
(158463, 'Iron Pellets', 'High pellets made of iron. Highly magnetic properties.', 12.5, '["iron","pellet","magnet","iron pellets", "iron pellet"]', 13),
(168463, 'Large Magnet', 'Large general purpose magnet, guaranteed to be attractive at great distances.', 112.5, '["large","magnet","magnetic"]', 11),
(169811, 'Bird Seed', '5lb bag of delicious seed, irresistable to any self-respecting bird.', 9.95, '["snack"]', 18),
(178463, 'Jet Bike Kit', 'Like a motorcycle, but without wheels.', 112.5, '["jet","fly","vehicle"]', 11),
(183774, 'Electric Skates', 'The latest in motorized speed skates. Dual electric motors allowing AWD and 0 - 60 acceleration times of less than 2 seconds. Sold by the pair.', 100.25, '["fast","vehicle","skate"]', 16),
(213734, 'Detonator', 'Can be used as an activation device to be attached to explosives', 72.51, '["dynamite","explosive","explode","bang"]', 19),
(213834, 'Smoke Screen Bomb', 'Creates a cloud of smoke, like fog, for camouflage', 18.45, '["smoke","hide"]', 73),
(213981, 'Big Bomb v2', 'Comes with a timer attachment. Guaranteed to explode eventually.', 115.45, '["explode","bomb","bang"]', 9),
(214754, 'Nitroglycerin', 'Explosive. HANDLE WITH EXTREME CARE.', 23.51, '["explosive","explode","bang"]', 19),
(233834, 'Artificial Hole', 'Looks like a real hole! Place it on any flat surface to fool your friends.', 21.65, '["fake"]', 11),
(243834, 'Dehydrated Boulders', 'Makes instant boulders with just a drop of water.', 31.29, '["rock", "water"]', 9),
(275383, 'Giant Kite Kit', 'Can be used as a regular kite, or can be used to drop weapons from the sky.', 4.5, '["flying","fly","large","vehicle"]', 23),
(275387, 'Giant Fly Paper', 'Like the stuff that catches flies, only GIANT. Very sticky.', 14.5, '["sticky","adhesive"]', 21),
(293121, 'Super Strong Glue', 'One half-gallon bucket of super strong glue. This stuff really sticks!', 7.53, '["sticky","adhesive"]', 23),
(293124, 'Invisible Paint', 'Makes any surface instantly invisible.', 17.51, '["paint","invisible"]', 13),
(313734, 'Trick balls', 'They explode on contact!', 42.15, '["explosive","explode","bang"]', 61),
(313834, 'Jet-Propelled Unicycle', 'faster than you think! Warning: no brakes.', 41.45, '["wheels","jet","speed","vehicle"]', 7),
(323333, 'Super Outfit', 'Despite appearances, it does not give anyone the ability to fly.', 8.72, '["fake","outfit","costume"]', 12),
(323401, 'Batman Outfit', 'This outfit will actually let you fly high in the sky!', 10.71, '["fake", "outfit","costume"]', 12),
(323433, 'Female Roadrunner Costume', 'You can disguise yourself as a female Road Runner,just watch out for Coyotes.',11.62, '["fake","bird","outfit","costume"]', 18),
(325601, 'Tornado Seeds', 'Lets you "seed" your own tornadoes. Just add water.', 25.75, '["tornado","wind","water","storm"]', 23),
(337734, 'Rocket Skates', 'The same rocket skates we developed back in the 50s. They are tried and true. Sold in pairs.', 150.87, '["rocket","speed","missile","vehicle","skate"]', 43),
(338914, 'Rocket Sled', 'Do it yourself rocket sled. Pairs well with railroad tracks.', 2150.17, '["rocket","speed","orbit","missile","vehicle"]', 7),
(339861, 'Railroad Tracks', 'Thirty miles worth of railroad tracks. Try it with the rocket sled.', 162150.11, '["railroad","iron"]', 2),
(357383, 'Giant Rubber Band', 'Useful for tripping road runners.', 4.5, '["stretchy","large"]', 51),
(358463, 'Axle Grease', 'Guaranteed to be super slippery.', 11.35, '["slide","grease","slippery","friction"]', 33),
(364163, 'Magnet Boots', 'Boots with super-strong magnets in the soles.', 62.15, '["footwear","magnet","magnetic"]', 21),
(387239, 'Indestructo Steel Ball', 'Lets you roll in a ball that''s literally indestructible. Warning: no steering control.', 187.11, '["steel","ball","indestructible","sturdy"]', 8),
(387463, 'Matches', 'Regular everyday matches, good for igniting things.', 0.75, '["fire","ignite"]', 210);

-- Sample Orders
--INSERT INTO orders (customer_id, order_date, total_amount) VALUES
--(1, '2024-03-10', 1215.50), -- Alice buys a Laptop and a Coffee Mug
--(2, '2024-03-12', 5.25);      -- Bob buys a Notebook
