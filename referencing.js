// Run after starships.py. This reuses the API Falcon instead of adding ship 37.
const lab = db.getSiblingDB('sparta_week06');
const names = ['Chewbacca', 'Han Solo', 'Nien Nunb', 'Lando Calrissian'];
const pilots = names.map(name => {
  const matches = lab.characters.find({name}, {_id: 1}).toArray();
  if (matches.length !== 1) throw new Error(`Ambiguous/missing pilot: ${name}`);
  return matches[0]._id;
});
const result = lab.starships.updateOne(
  {url: 'https://swapi.dev/api/starships/10/'}, {$set: {pilots}}
);
if (result.matchedCount !== 1) throw new Error('Run the starship import first');
const falcon = lab.starships.aggregate([
  {$match: {name: 'Millennium Falcon'}},
  {$lookup: {from: 'characters', localField: 'pilots', foreignField: '_id', as: 'pilot_details'}},
  {$project: {_id: 0, name: 1, pilot_names: '$pilot_details.name'}}
]).toArray();
if (falcon.length !== 1 || falcon[0].pilot_names.length !== 4) throw new Error('Broken Falcon links');
printjson(falcon);
if (lab.starships.countDocuments({}) !== 36) throw new Error('Expected 36 ships');
print('PASS: Millennium Falcon has four referenced pilots; 36 starships remain.');
