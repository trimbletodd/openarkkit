#!/usr/bin/python

#
# Repeat a given query until some condition is met; either:
# - no rows are affected
# - number of iteration exceeds predefined value
# - runtime exceeds predefined value
#
# Released under the BSD license
#
# Copyright (c) 2008-2010, Shlomi Noach
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#     * Neither the name of the organization nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import getpass
import MySQLdb
import sys
import time
import traceback
import warnings
from optparse import OptionParser

def parse_options():
    usage = "usage: oak-repeat-query [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-u", "--user", dest="user", default="", help="MySQL user")
    parser.add_option("-H", "--host", dest="host", default="localhost", help="MySQL host (default: localhost)")
    parser.add_option("-p", "--password", dest="password", default="", help="MySQL password")
    parser.add_option("--ask-pass", action="store_true", dest="prompt_password", help="Prompt for password")
    parser.add_option("-P", "--port", dest="port", type="int", default=3306, help="TCP/IP port (default: 3306)")
    parser.add_option("-S", "--socket", dest="socket", default="/var/run/mysqld/mysql.sock", help="MySQL socket file. Only applies when host is localhost")
    parser.add_option("-d", "--database", dest="database", help="Database name (required unless query uses fully qualified table names)")
    parser.add_option("", "--defaults-file", dest="defaults_file", default="", help="Read from MySQL configuration file. Overrides all other options")
    parser.add_option("-e", "--execute", dest="execute_query", help="Query (UPDATE or DELETE) to execute, which contains a chunk placeholder (required)")
    parser.add_option("-s", "--sleep-time", dest="sleep_time", type="int", default=1, help="Number of seconds between log polling (default: 1)")
    parser.add_option("", "--max-iterations", dest="max_iterations", type="int", default=None, help="Maximum number of iterations to execute")
    parser.add_option("", "--max-seconds", dest="max_seconds", type="int", default=None, help="Maximum number of seconds (clock time) to run")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Print user friendly messages")
    parser.add_option("", "--debug", dest="debug", action="store_true", help="Print stack trace on error")
    return parser.parse_args()


def verbose(message):
    if options.verbose:
        print "-- %s" % message

def print_error(message):
    sys.stderr.write("-- ERROR: %s\n" % message)

def open_connection():
    if options.defaults_file:
        conn = MySQLdb.connect(
            read_default_file = options.defaults_file,
            db = database_name)
    else:
        if options.prompt_password:
            password=getpass.getpass()
        else:
            password=options.password
        conn = MySQLdb.connect(
            host = options.host,
            user = options.user,
            passwd = password,
            port = options.port,
            db = database_name,
            unix_socket = options.socket)
    return conn;

def act_query(query):
    """
    Run the given query, commit changes
    """
    connection = conn
    cursor = connection.cursor()
    num_affected_rows = cursor.execute(query)
    cursor.close()
    connection.commit()
    return num_affected_rows


def get_row(query):
    connection = conn
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(query)
    row = cursor.fetchone()

    cursor.close()
    return row


def get_rows(query):
    connection = conn
    cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    return rows


def repeat_query():
    start_time = time.time()
    num_iterations = 0
    try:
        while True:
            num_affected_rows = act_query(options.execute_query)
            num_iterations += 1
            
            if num_affected_rows:
                verbose("Affected rows: %d." % num_affected_rows)
            else:
                verbose("No rows affected")
                
            if options.max_iterations is not None:
                if num_iterations >= options.max_iterations:
                    verbose("Max iterations (%d) reached. Terminating." % options.max_iterations)
                    return
            if options.max_seconds is not None:
                time_now = time.time()
                elapsed_seconds = time_now - start_time
                if elapsed_seconds >= options.max_seconds:
                    verbose("Max seconds (%d) reached. Terminating." % options.max_seconds)
                    return
            if options.max_iterations is None and options.max_seconds is None:
                # No explicit limitation set. Implicit limitation is no affected rows. 
                if not num_affected_rows:
                    verbose("Terminating due to no rows affected")
                    return
                
            if options.sleep_time:
                verbose("Will sleep for %.2f seconds" % (options.sleep_time,))
                time.sleep(options.sleep_time)
    except KeyboardInterrupt:
        # Catch a Ctrl-C. We still want to cleanly close connections
        verbose("User interrupt")


def exit_with_error(error_message):
    """
    Notify and exit.
    """
    print_error(error_message)
    exit(1)


try:
    try:
        conn = None
        reuse_conn = True
        (options, args) = parse_options()

        database_name = None
        if options.database:
            database_name=options.database

        if not options.execute_query:
            exit_with_error("No query defined")
            
        warnings.simplefilter("ignore", MySQLdb.Warning) 
        conn = open_connection()
                
        repeat_query()
    except Exception, err:
        if options.debug:
            traceback.print_exc()
        print err
finally:
    if conn:
        conn.close()
