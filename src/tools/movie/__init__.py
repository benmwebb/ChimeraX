#
# 'register_command' is called by the toolshed on start up
#
def register_command(command_name, bundle_info):
    from .moviecmd import register_movie_command
    register_movie_command()

