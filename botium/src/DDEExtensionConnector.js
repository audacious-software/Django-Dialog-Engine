const { exec } = require("child_process");

class DDEExtensionConnector {
  constructor ({ queueBotSays, caps }) {
    this.queueBotSays = queueBotSays
    this.caps = caps
  }

  UserSays (msg) {
    const me = this;
    
    const command_line = [
        'python',
        'manage.py',
        'send_cli_message',
        '"' + this.caps.DDE_DIALOG_USER_ID + '"',
        '"' + this.caps.DDE_DIALOG_SCRIPT_PATH + '"',
        '"' + msg['messageText'] + '"'
    ];

    console.log('Botium: %o', msg['messageText'].trim());

    exec(command_line.join(' '), (error, stdout, stderr) => {
        if (error) {
            console.log('error: %o', error);
            return;
        }
        
        if (stderr) {
            console.log('stderr: %o', stderr);
            return;
        }
        
        var lines = stdout.trim().split(/\r?\n/);
        
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            
            console.log('Django Dialog Engine: %o', line);
        }
        
        const botMsg = { messageText: stdout.trim() };

        setTimeout(() => me.queueBotSays(botMsg), 0);
    });
  }
}

module.exports = {
  PluginVersion: 1,
  PluginClass: DDEExtensionConnector
}
