'use strict';
const vscode = require('vscode');
const cp = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs/promises');
function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection('pydrift');
  const output = vscode.window.createOutputChannel('PyDrift');
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  status.text='PyDrift'; status.command='pydrift.audit'; status.tooltip='Audit execution configuration'; status.show();
  let busy=false, child=null;
  context.subscriptions.push(diagnostics,output,status,{dispose(){if(child)child.kill();}});
  async function choosePython(){
    const selected=await vscode.window.showOpenDialog({canSelectMany:false,openLabel:'Select trusted Python executable',filters:process.platform==='win32'?{'Executable':['exe']}:undefined});
    if(!selected)return;
    const executable=selected[0].fsPath;
    if(!path.isAbsolute(executable))throw new Error('Absolute executable required.');
    if((await fs.stat(executable)).isDirectory())throw new Error('Select an executable, not a directory.');
    const yes=await vscode.window.showWarningMessage(`Allow PyDrift to run this trusted Python 3.10+ executable? ${executable}`,{modal:true},'Approve');
    if(yes!=='Approve')return;
    await context.globalState.update('python',executable);
    return executable;
  }
  context.subscriptions.push(vscode.commands.registerCommand('pydrift.choosePython',async()=>{
    try {await choosePython();}catch(e){vscode.window.showErrorMessage(String(e));}
  }));
  context.subscriptions.push(vscode.commands.registerCommand('pydrift.resetPython',async()=>{
    await context.globalState.update('python',undefined);
    vscode.window.showInformationMessage('PyDrift executable approval removed.');
  }));
  context.subscriptions.push(vscode.commands.registerCommand('pydrift.audit',async()=>{
    if(busy)return vscode.window.showInformationMessage('PyDrift audit already running.');
    if(!vscode.workspace.isTrusted)return vscode.window.showWarningMessage('PyDrift requires a trusted workspace.');
    const folders=vscode.workspace.workspaceFolders||[];
    if(!folders.length)return vscode.window.showWarningMessage('Open a project folder first.');
    let folder=folders[0];
    if(folders.length>1){const item=await vscode.window.showQuickPick(folders.map(f=>({label:f.name,folder:f})));if(!item)return;folder=item.folder;}
    if(folder.uri.scheme!=='file')return vscode.window.showErrorMessage('Only filesystem folders are supported.');
    busy=true;
    try{
      const executable=context.globalState.get('python')||await choosePython();if(!executable)return;
      await vscode.window.withProgress({location:vscode.ProgressLocation.Notification,title:'PyDrift audit',cancellable:true},async(_,token)=>{
        const result=await new Promise((resolve,reject)=>{
          const proc=cp.execFile(executable,['-I','-S',context.asAbsolutePath('backend/audit.py'),folder.uri.fsPath],{cwd:context.extensionPath,timeout:20000,maxBuffer:4*1024*1024,windowsHide:true},(error,stdout,stderr)=>{
            subscription.dispose();child=null;
            if(error)return reject(new Error(token.isCancellationRequested?'Audit cancelled.':`Backend failed: ${stderr.slice(0,2000)||error.message}`));
            try{resolve(JSON.parse(stdout));}catch(e){reject(new Error('Backend returned invalid JSON.'));}
          });
          child=proc;
          const subscription=token.onCancellationRequested(()=>proc.kill());
        });
        if(token.isCancellationRequested)return;
        if(result.schema_version!==1||!Array.isArray(result.findings))throw new Error('Unsupported report schema.');
        diagnostics.clear();const groups=new Map();
        for(const finding of result.findings){
          if(typeof finding.file!=='string')continue;
          const full=path.resolve(folder.uri.fsPath,finding.file),relative=path.relative(folder.uri.fsPath,full);
          if(relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))continue;
          const uri=vscode.Uri.file(full);const line=Math.max(0,(finding.line||1)-1);
          const severity=finding.severity==='error'?vscode.DiagnosticSeverity.Error:finding.severity==='information'?vscode.DiagnosticSeverity.Information:vscode.DiagnosticSeverity.Warning;
          const d=new vscode.Diagnostic(new vscode.Range(line,0,line,1),finding.message,severity);d.code=finding.rule;d.source='PyDrift';
          const k=uri.toString();if(!groups.has(k))groups.set(k,{uri,list:[]});groups.get(k).list.push(d);
        }
        for(const g of groups.values())diagnostics.set(g.uri,g.list);
        output.clear();output.appendLine(JSON.stringify(result,null,2));output.show(true);
        status.text=`PyDrift: ${result.findings.length}`;
        vscode.window.showInformationMessage(`PyDrift: ${result.findings.length} findings, ${result.skipped.length} skipped files. Review Output for limits and evidence.`);
      });
    }catch(e){output.appendLine(String(e));vscode.window.showErrorMessage('PyDrift: '+e.message);}
    finally{busy=false;}
  }));
}
module.exports={activate};
