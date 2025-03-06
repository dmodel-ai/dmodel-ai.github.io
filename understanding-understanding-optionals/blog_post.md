---
title: Understanding Models Understanding Nullability
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
header-includes:
  - "<script src=\"sidenotes.js\"></script>"
bibliography: all.bib
linkReferences: true
abstract:

  Large language models have demonstrated an emergent ability to write
  code, but this ability requires an internal representation of
  program semantics that is little understood. Recent interpretability
  work has demonstrated that it is possible to extract internal
  representations of natural language concepts, raising the
  possibility that similar techniques could be used to extract program
  semantics concepts. In this work we study how large language models
  represent the nullability of program values. We measure how well
  models of various sizes complete programs that use nullable values,
  and then extract an internal representation of nullability.

---

# Introduction

The last five years have shown us that large language models, like
ChatGPT, Claude, and DeepSeek, can effectively write programs in many
domains.\AT{cite} This is an impressive capability given that writing
programs involves having a working understanding of many aspects of
program semantics. But though we know that these large models
understand programs to an extent, we still don't know many things
about these models understanding. We don’t know where they have deep
understanding and where they use heuristic reasoning, how they
represents program knowledge, and what kinds of situations will
challenge their capabilities.

Fortunately, recent work in model interpretability and representation
engineering\AT{which work?} has produced promising results which give
hope towards understanding more and more of the internal thought
processes of LLMs. Here at $d_{model}$ , we can think of no better
place to apply these new techniques than program understanding, where
there are many abstract properties that can be extracted with static
analysis. The vast work done in programming language theory over the
past hundred years provides many tools for scaling an understanding of
the internal thought processes of language models as they write
code.\AT{for examples, see cite, cite}

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, nullability. Nullable values are
represented differently across languages; as null pointers in C or
C++, with explicit Option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be nullable is necessary for
writing even basic code, and misunderstanding where they are nullable
can often be a source of bugs.

Do our models understand when a value is nullable? They must, to be
able to write code that deals with nullable values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.\todo{big claim!}

In this work:

* We introduce a microbenchmark of 15 programs that test basic model
  understanding of the flow of nullability through a program.

* We find that models begin to understand nullability in a local
  scope, satisfying many requirements of the python typechecker,
  before they start to understand how nullability flows across the
  program. ([@sec:testing])

* We find that models develop an internal concept of nullability as
  they scale up and are trained for longer. ([@sec:probing])

By the end of this post, we'll be able to build a probe that uses the
models activations to determine whether the model thinks a variable
read corresponds to a nullable variable, and show that internal
knowledge like so:

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading1 .inlinefig}

# Measuring Nullability Understanding Externally\AT{Externally = token-level?} {#sec:testing}

We begin by measuring model nullability understanding externally,
because it provides a "skyline," or upper-bound, on our ability to
extract internal concepts of nullability.

To measure nullability understanding externally, we ask the model to
complete simple partial programs that each require an understanding of
nullability. We refer to this suite of programs as
`NullabilityEval`. All of the tests in this benchmark suite are
composed of three functions or less, where the largest function is
seven lines long.

In our experiments we focus on the Pythia model suite [@biderman23],
as they have checkpoints available across training runs and various
scales. For measuring performance at larger sizes, we also include
Qwen2.5-Coder-32B\AT{cite}, Llama 3.1 405B Instruct\AT{cite}, and
DeepSeek-V3 (671B)\AT{cite}.

Each partial program is constructed such that there are a very limited
number of valid next lines in the program, and all of them demonstrate
some knowledge of the concept of nullability.

For example, our first test is:

*Test 1*^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.
The simplest way to do this is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. Since this is a pretty small space
of valid next lines, and all of them imply some understanding that
`num` may not be an `int`, we can use this program to test models for
nullability understanding by asking them to complete the program
another lines, then see if they produce something that matches these
valid lines with the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]:
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```

We find that Pythia models as small as 2.8b can successfully complete
this test, and that they learn to complete the test in the first third
of training. Consistent with observations that larger models are more sample-efficent \AT{cite}, larger Pythia models learn to complete this test earlier,
with Pythia 12b able to complete the test 20% of the way into training
and Pythia 2.8b able to complete it 28% of the way into
training.
\AT{HEREHEREHERE}

## Understanding Typing Rules

We see from the results of our first test that these models understand
nullability to some extent, but how deep is this understanding? To
start to quantify this, we give a syntax and semantics of a minimalist
subset of python that captures nullability in Appendix
[B.1](#sec:commonrules). We can then classify each partial program by
which program constructs and rules determine the nullability of the
target variable. For instance, Test 1 uses the List, Var, and For
rules.

So, do Pythia models 2.8b and up understand the semantics of these
three rules? As it turns out, not exactly. LLM's pick up on a lot of
information relationships in their training data that have statistical
correlation, without it necessarily being causal. What this means in
practice is that the models use things like variable names,
whitespace, statement orderings, and constant values to guess at
certain programming concepts.

For example, while many of the Pythia models
can complete:

```python
some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
result: list[int] = []
for num in some_numbers:
```

with a proper None check, changing the variable names and the
constants into:

```python
foo = [60, None, -33]
bar: list[int] = []
for corejoice in foo:
```

causes all the Pythia models to fail the test. Our results show that
the Pythia models rely heavily on features like variable naming when
reasoning about for loops.  Fortunately, many other typing rules, like
App (function application) and If_Out, do not exhibit such a strong
reliance on variable naming and constants.^[Stay tuned in the future
for a more in-depth exploration of how the models behave on individual
typing rules with different contexts and variable names.]

## Interprocedural Analysis

Even without obfuscating variable names, we can challenge the model by
adding layers of procedural indirection between the source and sink of
nullable values, thereby testing the model's _interprocedural_
understanding. Here's one such test:

*Test 2*
```python
from typing import Optional

def main() -> None:
    some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
    print(positive_numbers(some_numbers))

def positive_numbers(numbers: list[Optional[int]]) -> list[int]:
    result: list[int] = []
    for num in numbers:
```

In this test, we've taken the same logic and spread it across `main`
and another function, `positive_numbers`. Ideally, the model would
have to think a little harder to understand that `some_numbers` is
flowing from `main` through the function call into the body of
`positive_numbers`, causing the for loop body to need a `None`
check. In practice though, we find this test is actually *easier* for
the model to pass than Test 1, with models as small as Pythia 1b
passing it, and Pythia 12b learning to pass it 13% of the way into
training.

Because of the type annotations on the `positive_numbers` function,
the model doesn't need to pay attention to `main` at all. It can just
look at `positive_numbers`, and use the type annotation to know that
`numbers` contains `Optional[int]`s. Then, using the For rule it can
reason that `num` is nullable, so it must be checked for None before
proceeding. Looking at the type annotation turns out to be easier for
the model than scanning through a list to determine if there are None
and non-None values, resulting in an easier test overall.

So how would we *actually* test for interprocedural nullability
understanding in the model? Well, type annotations on Python functions
aren't required^[Technically this is known as "Optional typing", but
that's confusing in the context of this post. Not to be confused with
Gradual Typing, as introduced by Siek et al.], so we can instead
provide the model with an **unannotated** function, and see if it
still understands the flow of nullability. Here's a test that does
that:

*Test 3*
```python
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = process_value(value) + 1
    print(x)

def process_value(value):
```

Our base set of typing rules (listed as "Common Rules") don't handle
unannotated functions though, so we're going to have to add some more,
and here we're faced with a choice. The typing rules for normal Python
say that functions without return type annotations return the Any
type, and arguments without a type annotation have the type Any. In
fact, normal mypy will not check unannotated functions at *all*, even
for internal consistency; the `--check-untyped-defs` option will add
some checking back, but the types of arguments and return type will
still be Any. In Python, a value of any type can be converted to an
Any, and an Any can be converted to any value type.

This means that it would be technically type safe to do anything in
the body of `process_value`, including just returning the argument,
without a static type error. But at runtime, code that exploits this
fact would still fail.

If we want code that actually makes sense at runtime, we can
strengthen our type checker a bit by requiring that there be some
valid (non-Any) type for the function that works both at the call site
and in the function body. We still won't be requiring that this type
is actually written down anywhere, but we will be requiring that it
exist. We'll call this augmented type system mypy++.

In Appendix [B.2](#sec:unannotatedfuncs), we formalize the unannotated
function rules for mypy vs mypy++.

Test 3 is a bit trickier than our previous ones, and we find that
there's no consistent threshold of size at which Pythia models can
pass it. Pythia 1b, 2.8b, and 6.9b pass the test in their final
revisions, but Pythia 410m, 1.4b, and 12b don't. The bigger models all
have points in training where they can pass the test, but only
intermittently. Even 6.9b, the best performing size on this test,
fails the test in its second-to-last available revision^[Despite this,
it does pass the test 40% of the available revisions, about triple
what the other closest sizes can accomplish]. \AT{should we say
something about 12b not solving it?}

What the models *can* do well, however, is learn to pass these tests
in the mypy type system (as opposed to mypy++). In that system, where
they don't need to reason globally about the functions but only
locally, this test is one of the easiest for the models to
complete.^[This indicates that if you were to train a model using
typechecking as reinforcement feedback, you would want to use mypy++
and not mypy.]

Since this test suite is meant to be informative beyond the sizes of
the Pythia models, we also add another layer of indirection to add
more difficulty, in this test:

*Test 4*
```python
def handle_value(value, guard):
    if guard:
        return process_value("Foobar") + 1
    else:
        return process_value(value) + 1
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = handle_value(value, x < 10)
    print(x)

def process_value(value):
```

With two layers of indirection, we start to hit the limits of the
capabilities of even frontier models. Llama 405B is unable to
successfully pass this test, as are smaller models like Qwen Coder
32B, while DeepSeek V3 (671B parameters) is able to pass it. However,
Pythia 6.9B is still able to pass this test pretty consistently.

## Generating Type Annotations

Finally, we can test how good the models are at writing their own type
annotations for functions. Since most of the publicly available Python
code is not type-annotated, you could imagine that LLM's can reason
about dataflow correctness without annotations better than they can
write their own typing annotations. The next program tests the models
ability to write its own type annotations; the trailling colon makes
the type expression the only valid completion^[This is because
function declarations with a colon and no type, like `def fn(x:)` are
not valid python. Since we’ve already seen a usage of `get_square`
that is passed a None value, it wouldn’t be type-valid to complete the
program with just `int`. So a model can be tested on its understanding
of `Optional` annotations by seeing if its completion of the partial
program includes `Optional[int]`.]

*Test 5*:
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

None of the Pythia models are able to succesfully pass this test,
demonstrating that writing these annotations is indeed more difficult
for LLM's than implicitly reasoning about the types. Qwen Coder 32B is
also incapable of passing this test, but both Llama 405B and DeepSeek
V3 pass it.

## External Test Results Across Training and Scale

We wrote three variations of each of these tests, resulting in 15
tests total. Below, you can see the number of passing tests for each
model.

\todo{more through exploration of why?}

![A bar graph showing how several sizes of model perform on the
 high-level nullability tests](images/hl_model_results.svg){#fig:hl_scale}

In [@Fig:hl_scale], we can see the number of passing tests for each
model. We can see that generally models get better with scale.
\todo{I don't think this footnote is clear enough to add anything}
^[Pythia 12b performs worse than its 6.9b variant, though this might
be due to under-training at that size. Qwen 32B also performs about as
well as Pythia 6.9b, it's not clear if this is due to model
architecture or something else.] Model performance on these tests is
approximately logarithmic in model size: models of 2.8 billion
parameters can pass about half the tests, but it takes more than 405
billion parameters to pass all of the tests. This matches previous
post- and pre-training evaluations of the capabilities of large
language models\todo{cite, Kaplan et al, Chincilla}, indicating that
these tests are well distributed.

![A bar graph showing how the Pythia models perform in mypy vs
 mypy++](images/hl_mypy_vs_grep_models.svg){#fig:hl_mypy}

In [@Fig:hl_mypy], we can see the test result for the pythia models
using the mypy and mypy++ type systems ([@Fig:hl_scale] uses
mypy++). As we expected, the mypy results (red bar) are always above
the mypy++ results (blue bar), as mypy++ is a stricter type
system. There are six tests in the dataset involving non-annotated
functions, and using the weaker mypy typesystem causes up to five more
tests to pass than using mypy++^[We don't see all six non-annotated
function tests passing under mypy, because models can still fail these
tests by producing invalid syntax.]

Next, we want to understand the training dynamics at play here. Below
we can see how Pythia 6.9b performs on the tests during training from
step 2 to 143000:\todo{let's use the same axes scaling at the tigges
paper}

![A line graph showing how the performance of the Pythia
6.9 model changes during training](images/hl_revision_results.svg){#fig:hl_time}

Again, performance does not increase monotonically.  This plot is
quite noisy, so in the sequel, we will show smoothed^[rolling average
with a window size of 5] charts.

In the graph below, we see that each individual model also learns to
write code which typechecks under mypy before it learns to write code
which typechecks under mypy++ and throws no type errors at runtime.

![A graph showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that shows true
understanding.](images/hl_mypy_vs_grep_revisions.svg){#fig:hl_moral}

# Measuring Nullability Understanding Internally {#sec:probing}

At this point, we’ve figured out how to roughly measure nullability
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. In this section, we detail how we train reading vectors
[@sec:extraction], using prompts designed to make the model think about
the phenomena of interest [@sec:prompts]. Finally [@sec:results], we validate that
these probes improve their understanding of nullability over the course
of pretraining to the level that we expect from the external, or token-level
understanding evals we describe in the previous section.

## Background

<!--
As language models predict each token in a text, they run their tuned
circuits over all the previous text. Tokens are first embedded into a
high-dimensional "token space", and each layer of the transformer
model is made up of many parallel circuits which transform the
previous layers output into new embeddings in a new space. Each layer
can look not just at the output of the layer directly previous, but
actually all previous layers, through a channel called a residual
stream.

The paper presents two main approaches to interpreting a language
model; circuit-based, and representation-based. Circuit based
interpretability aims to pair down the network to a key set of
circuits which are sufficient to complete a particular task; this
allows practitioners to point to a particular part of the model and
say "this is where \<task\> is done", much like neuroscientists assign
functionality to different parts of our brain.

-->

In this section, we review representation engineering [@zou25] techniques that
we will use to look for linear representations of nullability inside the model.

@zou25 shows how representations can be extracted for
concepts like "happiness", "honesty", and "fairness". First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with "Pretend you’re a dishonest person. The Eiffel Tower is" and
"Pretend you’re an honest person. The Eiffel Tower is". Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is activated in the model during any given forward pass (e.g. for honesty,
this gives us a lie-detector).

![Figure from @zou25  showing the reading outputs for several
 concepts](images/zhou.png)

## Designing Prompts to Extract Nullability Activations {#sec:prompts}

We avoid dealing with the ambiguities of natural language by working in
a setting where the model needs only to complete code. analyze the nullability
of individual variable occurrences. Specifically, we probe for "the variable
I just generated refers to an nullable quantity", so our prompts looked like:

```python
def program_1() -> None:
  def find_value(data: List[int], target: int) -> Optional[int]:
    for value in data:
      if value == target:
      return value
    return None

  data = [1, 2, 3, 4, 5]
  target = 3
  result = find_value(data, target)
  if result
```

We queried o1, o1-mini, deepseek-coder, and claude-3.5-sonnet with the following prompt:

> Generate me 100 typed python programs that use the Optional type,
> along with type annotations for any undefined functions that they
> use. Make sure that the programs are unique, and each involves at
> least eight lines of logic. Number each program from 1 to 100. Please
> put all the programs in a single file, with a main function that tests
> each. Don't include any text before or after the code, just the
> code. I will be using mypy with the --strict option to check the code.

We label each variable read occurrence with nullability information derived
from mypy, and prompt the "model under test" with a prompt consisting of the
tokens up to and including the variable read occurrence.

## Extracting Reading Vectors {#sec:extraction}

Prior work focused their probing on a single layer, often handpicked
based on prior papers. We probe all
layers instead. We use Mass Mean Shift probing for each layer, because
it's been shown empirically [@li24] to generalize better in high
dimensional spaces than logistic regression^[Since we don't have
contrasting pairs, just labeled points, it's not possible to use the
PCA from contrasting pairs method used in @marks24 and @zou25. See
"Mass Mean Probing vs Linear Regression" in the appendix].

We then tested two methods for determining the relative importance of
the different layers --- either allowing the magnitude of the difference
of means vector to determine the importance of the layer in the final
probe, or to learn coefficients for each layer using linear
regression. We found that which method is more accurate on test data
varies over both model size and number of training steps.
\AT{should we mention this in the intro/contributions/or a "key results" section like tlide?}

![The performance of pure mass means probing vs mass means probing
 with linear regression for different Pythia model sizes. Binary-cross
 entropy is plotted, so lower is
 better.](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.

## Probing Results Across Training and Scale {#sec:results}

In this section, we study the performance of our nullability probes across time
and scale [@tigges24].
We use mass-means shift probing [@li24] on all layers,
and a linear regression to determine the weights of each layer.^[
@li24 and @zou25 suggest that mass means probes are best for reading,
while the direction perpendicular to the separating hyperplane is best for
intervention.
However, previous work leaves open the question of cross-layer weights. We use
LR on the cross-layer weights, thanks to our investigations above.]
\AT{see appendix D for mm vs LR}

![The performance, measured in binary cross-entropy, of each Pythia
 model size during pretraining. Since this graph is of loss, lower is
 better](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@Fig:models-and-steps], we plot loss against scale and time.
While we
measured accuracy for every available Pythia model size, we exclude
the smallest (14m) from this plot since it would
exist entirely above the top of the plot.
We notice turning points in the models' understanding of nullability at 1b parameters and \todo{number of tokens}.
We explore the texture of these in \todo{future work}.

## Visualizing Probe Outputs

Now that we've shown how to train these probes with increasing
accuracy, lets bring back the reading diagram we showed in the intro,
and go a bit more into depth with it.

We adapted this style of reading diagram from @zou25, but only show
the activations on tokens that represent variable loads, since that is
where we trained our probe^[There is also a much more practical
reason: right after the model has generated a variable that will be
written to, it often does not have access to the assigning expression
or type annotation, giving it no way to determine if the value will be
optional or now.]. For each measured token, we're running the model
until just after that token, then extracting it's hidden state and
measuring probe activation. We then color the box above that token
depending on the activations, and the scoring threshold inferred at
train-time^[Red tokens are significantly below the threshold, and
green tokens are significantly above it; tokens that scored near the
threshold would have a near-white color, but no such tokens appear in
this example.].

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading2 .inlinefig}

We can see here sixteen tokens that correspond to variable reads in
the program, and all but one are probed as non-optional
(correctly). The only nullable variable in this program is `result`,
since it comes from `find_value` which returns `Optional[int]`. So
when this variable appears for the first time in the `if` statement
checking if it's none, the model knows it is nullable, and the results
of the probe reflect that understanding. But when it appears a second
time on the next line, in the format string of `print`, the model no
longer thinks it is optional, since the body of this if statement only
runs if it is *not* `None`; the probe accurately reflects this.

# Related Work {#sec:related}

Our decision to use Pythia to study feature evolution across time and scale is
inspired by @tigges24 . They focus on classic circuits-centered
interpretability tasks such as IOI [@wang22], Gendered-Pronoun [@mathwin],
Greater-Than[@hanna23] , and SVA [@linzen16].

In our setting, we are more interested in how activations vary across inputs, to extract
representations of nullability. @zou25 surveys techniques for
representation engineering with linear probes. We apply similar techniques, but
to program semantics and dataflow instead of natural language.

@feng24predicate also study LLM's ability to reason about propositions, but in
a natural language setting, rather than a formal one.

Several techniques exist for constructing linear probes, but after
experimental measurement we followed the mass means shift from @li24. @li24
and @zhong23 discuss why mass mean probing might outperform linear regression.

# Future Work

\AT{Typing rules staircase plot}

# References {.unnumbered}
::: {#refs}
:::
