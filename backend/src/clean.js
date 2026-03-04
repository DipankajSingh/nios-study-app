const fs = require('fs');
const mockPath = '/home/dipankaj/Desktop/nios-study-app/backend/src/mockData.ts';
let content = fs.readFileSync(mockPath, 'utf8');

// We simply want to remove any dictionary block that contains "maths-12".
// Since entries look like:
//    {
//        id: 'maths-12',...
//    },
// We'll split by `    {\n` and filter them out.
const parts = content.split('    {\n');
const cleaned = parts.filter(part => !part.includes("'maths-12'")).join('    {\n');

fs.writeFileSync(mockPath, cleaned, 'utf8');
console.log('Cleaned mockData.ts successfully. Removed lines containing maths-12.');
