// Compile the pinned upstream solver modules into an isolated local tool runtime.
// Mesh2Motion MIT source stays in the ignored tooling checkout, never game code.
import fs from 'node:fs';
import path from 'node:path';
import ts from '../artifacts/rebuild_r48/tooling/rig-runtime/node_modules/typescript/lib/typescript.js';
const root=path.resolve(import.meta.dirname,'..');
const source=path.join(root,'artifacts/rebuild_r48/tooling/mesh2motion/src/lib');
const target=path.join(root,'artifacts/rebuild_r48/tooling/rig-runtime/compiled');
let count=0;
function compile(directory,relative=''){
  for(const name of fs.readdirSync(directory)){
    const sourceFile=path.join(directory,name),rel=path.join(relative,name);
    if(fs.statSync(sourceFile).isDirectory()){compile(sourceFile,rel);continue;}
    if(!name.endsWith('.ts')||name.endsWith('.test.ts'))continue;
    let output=ts.transpileModule(fs.readFileSync(sourceFile,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
    output=output.replace(/(from\s+['"])(\.[^'"]+)(['"])/g,(_,prefix,spec,suffix)=>prefix+(spec.endsWith('.ts')?spec.slice(0,-3)+'.js':path.extname(spec)?spec:spec+'.js')+suffix);
    const dest=path.join(target,rel.replace(/\.ts$/,'.js'));fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,output);count++;
  }
}
compile(source);
console.log(`Prepared ${count} upstream modules; only pure solver classes will execute.`);
