#!/usr/bin/env ruby
# encoding: utf-8
#
# when resolve merge conflict, 'git log commit' shows difference between first
# parent, this command shows difference between second parent
#
list = ARGV.delete('-l') || ARGV.delete('--list')
commit = ARGV.shift || 'HEAD'
if commit == '--'
    commit = 'HEAD'
    ARGV.unshift
end

other = ARGV.join ' ' # copy other parameters

if list
    extra_option = '--name-status'
else
    extra_option = ''
end

cmd1 = "git diff -w #{commit}^1..#{commit} #{other} #{extra_option}" # first parent
cmd2 = "git diff -w #{commit}^2..#{commit} #{other} #{extra_option}" # second parent
# puts '> ' + cmd1
puts '> ' + cmd2
system cmd2
