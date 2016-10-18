#!/usr/bin/env bash

# RUN: bash %s %T/filtered_build
# RUN: cd %T/filtered_build; %{intercept-build} --cdb result.json ./run.sh
# RUN: cd %T/filtered_build; cdb_diff result.json expected.json

set -o errexit
set -o nounset
set -o xtrace

# the test creates a subdirectory inside output dir.
#
# ${root_dir}
# ├── run.sh
# ├── expected.json
# └── src
#    ├── lib.c
#    └── main.c

root_dir=$1
mkdir -p "${root_dir}/src"

cat >> "${root_dir}/src/lib.c" << EOF
int foo() { return 2; }
EOF

cat >> "${root_dir}/src/main.c" << EOF
int main() { return 0; }
EOF


# set up platform specific linker options
PREFIX="fooflag"
if [ $(uname | grep -i "darwin") ]; then
  LD_FLAGS="-o lib${PREFIX}.dylib -dynamiclib -install_name @rpath/${PREFIX}"
else
  LD_FLAGS="-o lib${PREFIX}.so -shared -Wl,-soname,${PREFIX}"
fi


build_file="${root_dir}/run.sh"
cat >> ${build_file} << EOF
#!/usr/bin/env bash

set -o nounset
set -o xtrace

# set up unique names for this test

cd src

# non compilation calls shall not be in the result
"\$CC" -### -c main.c 2> /dev/null
"\$CC" -E -o "\$\$.i"       main.c
"\$CC" -S -o "\$\$.asm"     main.c
"\$CC" -c -o "\$\$.d"   -M  main.c
"\$CC" -c -o "\$\$.d"   -MM main.c

# preprocessor flags shall be filtered
"\$CC" -c -o one.o -fpic -MD  -MT target -MF one.d lib.c
"\$CC" -c -o two.o -fpic -MMD -MQ target -MF two.d lib.c

# linking shall not in the result
"\$CC" ${LD_FLAGS} one.o two.o

# linker flags shall be filtered
"\$CC" -o "${PREFIX}_one" "-l${PREFIX}"  -L.  main.c
"\$CC" -o "${PREFIX}_two" -l "${PREFIX}" -L . main.c

true;
EOF
chmod +x ${build_file}

cat >> "${root_dir}/expected.json" << EOF
[
    {
        "command": "cc -c -o one.o -fpic lib.c", 
        "directory": "${root_dir}/src", 
        "file": "${root_dir}/src/lib.c"
    }, 
    {
        "command": "cc -c -o two.o -fpic lib.c", 
        "directory": "${root_dir}/src", 
        "file": "${root_dir}/src/lib.c"
    }, 
    {
        "command": "cc -c -o fooflag_one main.c", 
        "directory": "${root_dir}/src", 
        "file": "${root_dir}/src/main.c"
    }, 
    {
        "command": "cc -c -o fooflag_two main.c", 
        "directory": "${root_dir}/src", 
        "file": "${root_dir}/src/main.c"
    }
]
EOF