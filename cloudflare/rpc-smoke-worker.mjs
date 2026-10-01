/** Local-only private service binding harness; never deploy this entry. */
export default {async fetch(request,env){
  const {scope,snapshot}=await request.json();
  const result=await env.TOOL.assess(JSON.stringify(scope),JSON.stringify(snapshot));
  return new Response(result,{headers:{'Content-Type':'application/json'}});
}};
