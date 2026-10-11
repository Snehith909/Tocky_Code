/**
 * Vulnerable JavaScript test fixture for CodeGuard AI evaluation.
 * Demonstrates command injection, prototype pollution, and hardcoded secret.
 */

const { exec } = require('child_process');

const JWT_SECRET = "sk-secret-token-key-123456789";

function executeUserCommand(targetHost) {
  // Vulnerability: Command Injection
  exec(`ping -c 4 ${targetHost}`, (err, stdout) => {
    console.log(stdout);
  });
}

function mergeObjects(target, source) {
  // Vulnerability: Prototype Pollution
  for (let key in source) {
    target.__proto__ = source[key];
  }
  return target;
}

module.exports = { executeUserCommand, mergeObjects };
